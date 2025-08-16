from collections import defaultdict
from datetime import datetime, timezone
import os  # if not already imported
import json, random, datetime, os, hashlib, base64, time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from dateutil.relativedelta import relativedelta
from authlib.integrations.starlette_client import OAuth
from starlette.responses import RedirectResponse
from pywebpush import webpush, WebPushException
from typing import List, Dict, Any, Optional

from config import ENABLE_GOOGLE, LOCAL_ONLY, RETENTION_DAYS, VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_CLAIMS, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER, REDIRECT_URI

# ---------- Models ----------
class Parent(BaseModel):
    email: str
    name: Optional[str] = None
    org: Optional[str] = None

class Child(BaseModel):
    name: str
    age_years: float = Field(ge=0, le=12)
    language: str = "en"  # 'en' or 'nl'
    temperament: Optional[str] = "balanced"

class DayPlanRequest(BaseModel):
    child: Child
    wake_time: str  # "07:00"
    available_blocks_min: List[int] = [20, 30, 40]
    focus: Optional[str] = "calm"  # calm | active | learning

class ActivitySuggestRequest(BaseModel):
    child: Child
    minutes: int = 20
    mode: str = "solo"  # solo | together

class StoryRequest(BaseModel):
    child: Child
    theme: str = "adventure"
    length_min: int = 4
    bilingual: bool = False

class SessionStartRequest(BaseModel):
    child: Child
    duration_min: int = 30
    goal: str = "engage" # engage | calm | learn

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]

# ---------- App ----------
app = FastAPI(title="Haven AI Nanny — Pro")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def load_json(path: str):
    with open(path,"r",encoding="utf-8") as f: return json.load(f)

ACTIVITIES = load_json("content/activities.json")
ST_EN = load_json("content/stories_en.json")
ST_NL = load_json("content/stories_nl.json")

DB: Dict[str, Any] = {
    "parents": [], "children": [], "sessions": [], "time_saved_min": 0,
    "subscriptions": [], "events_path": "data/events.jsonl", "orgs": {}
}
os.makedirs("data", exist_ok=True)
if not os.path.exists(DB["events_path"]):
    with open(DB["events_path"],"w") as _f: pass

def log_event(kind: str, payload: Dict[str, Any]):
    entry = {"ts": time.time(), "kind": kind, "payload": payload}
    with open(DB["events_path"],"a") as f:
        f.write(json.dumps(entry)+"\n")

# Ensure a writable events log path even on MVP
if "events_path" not in DB:
    DB["events_path"] = "data/events.jsonl"
os.makedirs("data", exist_ok=True)
# Create the file if it doesn't exist
try:
    open(DB["events_path"], "a").close()
except Exception:
    pass

# ---------- Meal Planner ----------
MEAL_DB = {
    "breakfast": [
        {
            "name": "Oatmeal with banana",
            "ingredients": {"rolled oats (g)": 40, "milk or alt (ml)": 200, "banana": 0.5, "honey (tsp)": 1},
            "budget": {"low": {}, "mid": {"honey (tsp)": 1}, "high": {"berries (g)": 30}},
            "prep_time_min": 6,
            "instructions": [
                "Heat milk in a small pot until steaming (do not boil).",
                "Stir in oats; simmer 3–4 minutes until thick.",
                "Slice banana; top oatmeal with banana and honey.",
                "High budget: add berries on top."
            ],
            "notes": "Use water for lighter oatmeal. Cool before serving young children."
        },
        {
            "name": "Yogurt & granola cup",
            "ingredients": {"plain yogurt (g)": 150, "granola (g)": 30, "apple": 0.5},
            "budget": {"low": {}, "mid": {"granola (g)": 35}, "high": {"berries (g)": 40, "honey (tsp)": 1}},
            "prep_time_min": 4,
            "instructions": [
                "Layer yogurt in a cup or bowl.",
                "Top with granola and chopped apple.",
                "High budget: add berries and a drizzle of honey."
            ],
            "notes": "Use low‑sugar granola for kids."
        }
    ],
    "lunch": [
        {
            "name": "Turkey & cheese sandwich",
            "ingredients": {"wholegrain bread (slices)": 2, "turkey slices": 2, "cheese slice": 1, "cucumber (slices)": 4},
            "budget": {"low": {"cheese slice": 0.5}, "mid": {}, "high": {"tomato (slices)": 2, "spinach handful": 1}},
            "prep_time_min": 5,
            "instructions": [
                "Layer turkey and cheese between bread.",
                "Add cucumber; high budget: add tomato and spinach.",
                "Cut into small squares or triangles."
            ],
            "notes": "Swap turkey for hummus for a veggie option."
        },
        {
            "name": "Veggie pasta",
            "ingredients": {"pasta (g)": 60, "tomato sauce (g)": 120, "frozen veggies (g)": 60},
            "budget": {"low": {}, "mid": {"parmesan (tbsp)": 1}, "high": {"olive oil (tsp)": 1, "fresh basil (leaves)": 3}},
            "prep_time_min": 15,
            "instructions": [
                "Boil pasta in salted water until tender.",
                "Warm sauce with frozen veggies in a pan.",
                "Stir pasta into sauce.",
                "Mid: sprinkle parmesan. High: add olive oil and basil."
            ],
            "notes": "Use small pasta shapes for toddlers."
        }
    ],
    "snack": [
        {
            "name": "Carrot sticks & hummus",
            "ingredients": {"carrot": 0.5, "hummus (tbsp)": 2},
            "budget": {"low": {}, "mid": {}, "high": {"cucumber (sticks)": 4}},
            "prep_time_min": 3,
            "instructions": [
                "Cut carrot into sticks.",
                "Serve with hummus. High budget: add cucumber sticks."
            ],
            "notes": "Steam carrots briefly for very young children."
        },
        {
            "name": "Apple slices & peanut butter",
            "ingredients": {"apple": 0.5, "peanut butter (tbsp)": 1},
            "budget": {"low": {}, "mid": {}, "high": {"raisins (tbsp)": 1}},
            "prep_time_min": 2,
            "instructions": [
                "Slice apple thinly.",
                "Serve with peanut butter. High budget: sprinkle raisins."
            ],
            "notes": "Check for nut allergies; use seed butter if needed."
        }
    ],
    "dinner": [
        {
            "name": "Chicken, rice & broccoli",
            "ingredients": {"chicken (g)": 70, "rice (g)": 50, "broccoli (g)": 60},
            "budget": {"low": {}, "mid": {"soy sauce (tsp)": 1}, "high": {"sesame oil (tsp)": 0.5}},
            "prep_time_min": 20,
            "instructions": [
                "Steam or boil broccoli until tender.",
                "Cook rice according to package.",
                "Pan-cook diced chicken until no longer pink.",
                "Combine on plate. Mid: soy sauce. High: sesame oil drizzle."
            ],
            "notes": "Shred chicken for younger kids."
        },
        {
            "name": "Mild veggie chili",
            "ingredients": {"kidney beans (g)": 80, "sweetcorn (g)": 40, "tomato passata (g)": 120, "rice (g)": 50},
            "budget": {"low": {}, "mid": {"cheddar (tbsp)": 1}, "high": {"avocado": 0.25}},
            "prep_time_min": 25,
            "instructions": [
                "Simmer beans, corn, and passata 10–12 minutes (no chili heat).",
                "Cook rice separately.",
                "Serve chili over rice. Mid: cheddar. High: sliced avocado."
            ],
            "notes": "Rinse canned beans to reduce sodium."
        }
    ]
}

def _pick(lst, i):
    # deterministic rotate
    return lst[i % len(lst)]

def _merge_ingredients(base: Dict[str, float], extra: Dict[str, float]):
    out = base.copy()
    for k, v in extra.items():
        out[k] = out.get(k, 0) + v
    return out

def _scale_for_age(ingredients: Dict[str, float], age_years: float) -> Dict[str, float]:
    # simple scaling: 0.5x for <=2y, 0.75x for <=4y, 1.0x otherwise
    if age_years <= 2: factor = 0.5
    elif age_years <= 4: factor = 0.75
    else: factor = 1.0
    return {k: round(v * factor, 2) for k, v in ingredients.items()}

from pydantic import BaseModel
class MealPlanRequest(BaseModel):
    child: Dict[str, Any]
    days: int = 7
    budget: str = "mid"  # low | mid | high

@app.post("/mealplan/generate")
def mealplan_generate(req: MealPlanRequest):
    budget = req.budget.lower()
    if budget not in ("low","mid","high"):
        budget = "mid"
    days = max(1, min(14, req.days))
    age = float(req.child.get("age_years", 4.0))

    plan = []
    grocery: Dict[str, float] = {}
    grocery_links: Dict[str, list] = {}  # ingredient -> [recipe labels]

    def link_ingredient(ing_name: str, recipe_label: str):
        grocery_links.setdefault(ing_name, [])
        if recipe_label not in grocery_links[ing_name]:
            grocery_links[ing_name].append(recipe_label)

    def assemble(label_prefix: str, item: dict):
        base = item["ingredients"]
        extras = item["budget"].get(budget, {})
        merged = _merge_ingredients(base, extras)
        ing = _scale_for_age(merged, age)
        recipe_label = f"Day {label_prefix} — {item['name']}"
        # collect totals + link each ingredient to this recipe
        for k, v in ing.items():
            grocery[k] = round(grocery.get(k, 0) + v, 2)
            link_ingredient(k, recipe_label)
        return {
            "name": item["name"],
            "ingredients": ing,
            "prep_time_min": item.get("prep_time_min"),
            "instructions": item.get("instructions", []),
            "notes": item.get("notes", "")
        }

    for d in range(days):
        b = _pick(MEAL_DB["breakfast"], d)
        l = _pick(MEAL_DB["lunch"], d)
        s = _pick(MEAL_DB["snack"], d)
        dn = _pick(MEAL_DB["dinner"], d)

        day_num = d + 1
        day_plan = {
            "day": day_num,
            "breakfast": assemble(f"{day_num} Breakfast", b),
            "lunch":     assemble(f"{day_num} Lunch",     l),
            "snack":     assemble(f"{day_num} Snack",     s),
            "dinner":    assemble(f"{day_num} Dinner",    dn),
        }
        plan.append(day_plan)

    return {
        "ok": True,
        "days": days,
        "budget": budget,
        "plan": plan,
        "grocery_list": grocery,
        "grocery_links": grocery_links  # NEW: which recipes use each ingredient
    }
        plan.append(day_plan)

    return {"ok": True, "days": days, "budget": budget, "plan": plan, "grocery_list": grocery}

class GroceryDownloadRequest(BaseModel):
    grocery_list: Dict[str, float]

@app.post("/mealplan/groceries.txt")
def mealplan_groceries_txt(req: GroceryDownloadRequest):
    lines = ["Haven Grocery List"]
    for k, v in sorted(req.grocery_list.items()):
        lines.append(f"- {k}: {v}")
    text = "\n".join(lines)
    return PlainTextResponse(text, media_type="text/plain")
    
# ---------- Basic endpoints ----------
@app.post("/signup")
def signup(parent: Parent):
    DB["parents"].append(parent.model_dump())
    log_event("signup", parent.model_dump())
    return {"ok": True, "parent": parent}

@app.post("/child")
def add_child(child: Child):
    DB["children"].append(child.model_dump())
    log_event("child_add", child.model_dump())
    return {"ok": True, "child": child}

def plan_block(minutes: int, child: Child, focus: str):
    lang = child.language if child.language in ACTIVITIES else "en"
    candidates = [a for a in ACTIVITIES[lang]["solo"] if a["minutes"][0] <= minutes <= a["minutes"][1] and child.age_years >= a["age_min"]]
    if focus != "active":
        candidates = [a for a in candidates if a["energy"] != "active"] or candidates
    if not candidates: candidates = ACTIVITIES[lang]["solo"]
    a = random.choice(candidates)
    return {"minutes": minutes, "activity": a["name"], "energy": a["energy"]}

@app.post("/plan/day")
def plan_day(req: DayPlanRequest):
    blocks = [{"time": req.wake_time, "title": "Wake-up & check-in"}]
    t = datetime.datetime.strptime(req.wake_time, "%H:%M")
    for m in req.available_blocks_min:
        block = plan_block(m, req.child, req.focus)
        t_end = t + datetime.timedelta(minutes=m)
        blocks.append({"start": t.strftime("%H:%M"), "end": t_end.strftime("%H:%M"), "plan": block})
        t = t_end + datetime.timedelta(minutes=5)
    log_event("plan_day", {"child": req.child.model_dump(), "blocks": req.available_blocks_min})
    return {"ok": True, "blocks": blocks, "note": "Adult supervision required."}

@app.post("/activities/suggest")
def activities_suggest(req: ActivitySuggestRequest):
    lang = req.child.language if req.child.language in ACTIVITIES else "en"
    pool = ACTIVITIES[lang][req.mode]
    out = [a for a in pool if a["minutes"][0] <= req.minutes <= a["minutes"][1] and req.child.age_years >= a["age_min"]]
    if not out: out = pool
    log_event("activities_suggest", {"minutes": req.minutes, "mode": req.mode})
    return {"ok": True, "suggestions": out[:5]}

@app.post("/story/generate")
def story_generate(req: StoryRequest):
    lang = req.child.language
    seeds = ST_NL if lang == "nl" else ST_EN
    seed = random.choice(seeds)
    child_name = req.child.name or ("je kind" if lang=="nl" else "your child")
    story = seed["template"].format(child=child_name)
    if req.bilingual:
        if lang == "nl":
            alt = random.choice(ST_EN)["template"].format(child=child_name); story += "\n\n[English] " + alt
        else:
            alt = random.choice(ST_NL)["template"].format(child=child_name); story += "\n\n[Nederlands] " + alt
    log_event("story", {"title": seed["title"], "lang": lang})
    return {"ok": True, "title": seed["title"], "story": story}

@app.post("/session/start")
def session_start(req: SessionStartRequest):
    flow = [
        {"phase":"warmup","minutes":5,"action":"calm breathing + choose mascot plush"},
        {"phase":"core","minutes":max(5, req.duration_min-10),"action":"guided solo activity"},
        {"phase":"winddown","minutes":5,"action":"short story + tidy-up song"}
    ]
    DB["sessions"].append({"child": req.child.model_dump(), "duration": req.duration_min})
    DB["time_saved_min"] += req.duration_min
    log_event("session_start", {"duration": req.duration_min})
    return {"ok": True, "flow": flow, "safety":"Adult must be reachable at all times."}

@app.get("/metrics/timesaved")
def metrics_timesaved():
    return {"ok": True, "minutes_saved_total": DB["time_saved_min"], "sessions": len(DB["sessions"])}

@app.get("/admin/metrics/aggregate")
def admin_metrics():
    return {
        "sessions": len(DB.get("sessions", [])),
        "minutes_saved_total": DB.get("time_saved_min", 0),
        "children": len(DB.get("children", [])),
        "parents": len(DB.get("parents", [])),
    }

@app.get("/admin/metrics/timeseries")
def admin_timeseries():
    """
    Returns daily totals of minutes saved based on recorded sessions.
    Also parses the events log (if present) for historical sessions.
    """
    series = defaultdict(int)

    # 1) Count current in‑memory sessions
    for s in DB.get("sessions", []):
        # Bucket into "today" for simplicity (MVP doesn’t timestamp sessions)
        today = datetime.now(timezone.utc).date()
        series[str(today)] += int(s.get("duration", 0))

    # 2) Parse events log if it exists (Pro version writes 'session_start' events)
    path = DB.get("events_path")
    try:
        with open(path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("kind") == "session_start":
                        dt = datetime.fromtimestamp(obj["ts"], tz=timezone.utc).date()
                        series[str(dt)] += int(obj["payload"].get("duration", 0))
                except Exception:
                    pass
    except Exception:
        pass

    items = sorted(series.items(), key=lambda x: x[0])
    return {"ok": True, "days": [d for d,_ in items], "minutes": [m for _,m in items]}
    
# ---------- Calendar (.ics) ----------
from pydantic import BaseModel
class ICSRequest(BaseModel):
    child: Child
    date: str  # YYYY-MM-DD
    plan: List[Dict[str, Any]]

def ics_escape(s:str)->str:
    return s.replace(",", r"\,").replace(";", r"\;")

from fastapi.responses import PlainTextResponse
@app.post("/integrations/calendar/ics")
def make_ics(req: ICSRequest):
    lines = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Haven//AI Nanny//EN"]
    for item in req.plan:
        title = item.get("plan",{}).get("activity","Haven Activity")
        start = item.get("start"); end = item.get("end")
        if not (start and end): continue
        dt = datetime.datetime.strptime(req.date+" "+start, "%Y-%m-%d %H:%M")
        dt_end = datetime.datetime.strptime(req.date+" "+end, "%Y-%m-%d %H:%M")
        uid = hashlib.sha1(f"{req.child.name}{dt}".encode()).hexdigest()+"@haven"
        lines += ["BEGIN:VEVENT",
                  f"UID:{uid}",
                  f"DTSTAMP:{datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                  f"DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}",
                  f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                  f"SUMMARY:{ics_escape(title)}",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return PlainTextResponse("\\r\\n".join(lines), media_type="text/calendar")

# ---------- Web Push ----------
class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]

@app.get("/notifications/publickey")
def publickey():
    return {"key": VAPID_PUBLIC_KEY}

@app.post("/notifications/register")
def notifications_register(sub: PushSubscription):
    subs_path = "data/subscriptions.json"
    try:
        data = json.load(open(subs_path,"r"))
    except Exception:
        data = []
    if not any(s.get("endpoint")==sub.endpoint for s in data):
        data.append(sub.model_dump())
        json.dump(data, open(subs_path,"w"))
    log_event("push_register", {"count": len(data)})
    return {"ok": True, "registered": len(data)}

from pydantic import BaseModel
class PushMessage(BaseModel):
    title: str
    body: str

@app.post("/notifications/test")
def notifications_test(msg: PushMessage):
    subs_path = "data/subscriptions.json"
    if not os.path.exists(subs_path): 
        raise HTTPException(400,"No subscriptions")
    subs = json.load(open(subs_path,"r"))
    sent = 0
    for s in subs:
        try:
            webpush(subscription_info=s, data=json.dumps({"title": msg.title, "body": msg.body}),
                    vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims=VAPID_CLAIMS)
            sent += 1
        except WebPushException:
            continue
    log_event("push_send", {"attempted": len(subs), "sent": sent})
    return {"ok": True, "sent": sent}

# ---------- Privacy Controls ----------
@app.get("/privacy/export")
def privacy_export():
    bundle = {"parents": DB["parents"], "children": DB["children"], "sessions": DB["sessions"]}
    return bundle

@app.delete("/privacy/child/{name}")
def privacy_delete_child(name: str):
    before = len(DB["children"])
    DB["children"] = [c for c in DB["children"] if c.get("name") != name]
    after = len(DB["children"])
    log_event("child_delete", {"name": name})
    return {"ok": True, "removed": before - after}

@app.delete("/privacy/wipe")
def privacy_wipe():
    DB["children"].clear(); DB["parents"].clear(); DB["sessions"].clear(); DB["time_saved_min"] = 0
    log_event("wipe", {}); 
    return {"ok": True}

@app.post("/privacy/maintenance")
def privacy_maintenance():
    cutoff = time.time() - (RETENTION_DAYS*24*3600)
    path = DB["events_path"]
    if not os.path.exists(path): return {"ok": True, "pruned": 0}
    kept = []
    with open(path) as f:
        for line in f:
            try:
                item = json.loads(line); 
                if item.get("ts",0) >= cutoff: kept.append(line)
            except: pass
    with open(path,"w") as f:
        for line in kept: f.write(line)
    return {"ok": True, "kept": len(kept)}

# ---------- Employer / SSO Scaffold ----------
class Org(BaseModel):
    org_id: str
    name: str
    domain: Optional[str] = None

@app.post("/admin/orgs")
def create_org(org: Org):
    DB["orgs"][org.org_id] = org.model_dump()
    log_event("org_create", org.model_dump())
    return {"ok": True, "orgs": list(DB["orgs"].values())}

@app.get("/admin/metrics/aggregate")
def admin_metrics():
    return {
        "sessions": len(DB["sessions"]),
        "minutes_saved_total": DB["time_saved_min"],
        "children": len(DB["children"]),
        "parents": len(DB["parents"]),
    }

@app.get("/sso/mock/login")
def sso_mock_login(email: str = "user@example.com", org_id: str = "demo"):
    DB["parents"].append({"email": email, "name": "Mock User", "org": org_id})
    log_event("sso_mock", {"email": email, "org": org_id})
    return {"ok": True, "email": email, "org": org_id}

# OAuth scaffold (disabled by default)
oauth = OAuth()
if ENABLE_GOOGLE:
    oauth.register(
        name="google",
        client_id=OIDC_CLIENT_ID,
        client_secret=OIDC_CLIENT_SECRET,
        server_metadata_url=f"{OIDC_ISSUER}/.well-known/openid-configuration",
        client_kwargs={"scope":"openid email profile"}
    )

@app.get("/integrations/google/auth-url")
def google_auth_url():
    if not ENABLE_GOOGLE: 
        return {"ok": False, "message":"Google integration disabled; set ENABLE_GOOGLE=True in config.py"}
    return {"ok": True, "auth_url": "/integrations/google/login"}  # stub for local

@app.get("/integrations/google/login")
async def google_login(request: Request):
    if not ENABLE_GOOGLE: raise HTTPException(400,"Disabled")
    redirect_uri = REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/integrations/google/callback")
async def google_callback(request: Request):
    if not ENABLE_GOOGLE: raise HTTPException(400,"Disabled")
    token = await oauth.google.authorize_access_token(request)
    user = token.get("userinfo", {})
    DB["parents"].append({"email": user.get("email"), "name": user.get("name")})
    log_event("sso_google", {"email": user.get("email")})
    return RedirectResponse(url="/")
