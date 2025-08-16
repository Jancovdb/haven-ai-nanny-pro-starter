const API_BASE = "https://haven-ai-nanny-pro-starter.onrender.com";

function todayISO() {
  const d = new Date();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${d.getFullYear()}-${m}-${day}`;
}

let child = {name:"Ava", age_years:4.0, language:"en", temperament:"balanced"};

document.getElementById('saveChild').onclick = async () => {
  child = {
    name: document.getElementById('cname').value || "Your child",
    age_years: parseFloat(document.getElementById('cage').value || "4.0"),
    language: document.getElementById('clang').value,
    temperament: "balanced"
  };
  const res = await fetch(API_BASE + "/child", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(child)});
  const data = await res.json();
  document.getElementById('childStatus').textContent = data.ok ? "Saved!" : "Failed";
};

document.getElementById('suggestAct').onclick = async () => {
  const minutes = parseInt(document.getElementById('amin').value || "20");
  const mode = document.getElementById('amode').value;
  const res = await fetch(API_BASE + "/activities/suggest", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, minutes, mode})});
  const data = await res.json();
  document.getElementById('actOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('storyBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/story/generate", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, theme: document.getElementById('theme').value, bilingual: document.getElementById('bilingual').checked})});
  const data = await res.json();
  document.getElementById('storyOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('sessionBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/session/start", {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({child, duration_min:30, goal:"engage"})});
  const data = await res.json();
  document.getElementById('sessionOut').textContent = JSON.stringify(data, null, 2);
};

document.getElementById('metricsBtn').onclick = async () => {
  const res = await fetch(API_BASE + "/metrics/timesaved");
  const data = await res.json();
  document.getElementById('metricsOut').textContent = JSON.stringify(data, null, 2);
};

// Set default date on load
document.addEventListener('DOMContentLoaded', () => {
  const pd = document.getElementById('planDate');
  if (pd && !pd.value) pd.value = todayISO();
});

document.getElementById('exportICS').onclick = async () => {
  const status = document.getElementById('icsStatus');
  status.textContent = "Creating plan...";

  const wake = document.getElementById('wakeTime').value || "07:00";
  const blocksStr = document.getElementById('blocks').value || "20,30,40";
  const date = document.getElementById('planDate').value || todayISO();
  const available_blocks_min = blocksStr.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n) && n > 0);

  const planRes = await fetch(`${API_BASE}/plan/day`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ child, wake_time: wake, available_blocks_min, focus: "calm" })
  });

  if (!planRes.ok) {
    status.textContent = "Failed to create plan. Save a child profile first.";
    return;
  }
  const planData = await planRes.json();

  const icsRes = await fetch(`${API_BASE}/integrations/calendar/ics`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ child, date, plan: planData.blocks.filter(b => b.start && b.end) })
  });

  if (!icsRes.ok) {
    status.textContent = "Failed to generate ICS file.";
    return;
  }

  const icsText = await icsRes.text();
  const blob = new Blob([icsText], {type: "text/calendar;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const childName = (child?.name || "child").replace(/\s+/g,'_');
  a.download = `haven_plan_${childName}_${date}.ics`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);

  status.textContent = "Downloaded .ics! Import it into your calendar.";
};
