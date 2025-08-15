import os, sys, json
from fastapi.testclient import TestClient
sys.path.append(os.path.dirname(__file__) + "/../backend")
from app import app
client = TestClient(app)

def test_ics():
    child = {"name":"Ava","age_years":4.0,"language":"en"}
    plan = [{"start":"09:00","end":"09:20","plan":{"activity":"Sticker sorting"}}]
    r = client.post("/integrations/calendar/ics", json={"child":child,"date":"2025-08-15","plan":plan})
    assert r.status_code == 200
    assert "BEGIN:VCALENDAR" in r.text
