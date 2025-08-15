# Haven — AI Nanny (Pro Starter) 🚀

This upgrade extends the MVP with **calendar integrations, web push notifications, bilingual UI (EN/NL), privacy controls (local-only mode), and an employer benefits edition with SSO scaffolding & analytics.**

> **Safety:** Haven is a *parenting co‑pilot*, not a replacement for human supervision. Do **not** leave children unattended.

## Quick Start
### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```
API: http://127.0.0.1:8000  (Docs: `/docs`)

### Frontend
Open `frontend/index.html` and keep `API_BASE` pointing at your backend.

---

## New Features

### 1) Calendar Integrations
- Generate **.ics** files from day plans: `POST /integrations/calendar/ics` -> returns ICS string.
- Google Calendar OAuth **scaffold** (via OpenID Connect / OAuth2): endpoints `GET /integrations/google/auth-url` and callback stub. Fill in `backend/config.py` with your credentials and enable `ENABLE_GOOGLE=True`.

### 2) Web Push Notifications
- Register push subscription: `POST /notifications/register` (stores subscription JSON in `backend/data/subscriptions.json`).
- Send a test notification: `POST /notifications/test` with a `title` and `body`.
- Frontend includes **Service Worker** and registration logic. Configure VAPID keys in `backend/config.py`.

### 3) Bilingual UX (EN/NL)
- Frontend strings in `/frontend/assets/i18n/en.json` and `nl.json`.
- Language switcher in the header. Persists choice in `localStorage`.
- Content seeds already include EN/NL activities and stories.

### 4) Privacy / Local‑Only Mode
- `backend/config.py` includes `LOCAL_ONLY=True` (default). When enabled, the app avoids outbound calls and marks all processing as on-device / on-server only.
- Data minimization, **export** and **delete** endpoints:
  - `GET /privacy/export` — dumps your data bundle (JSON)
  - `DELETE /privacy/child/{name}` — deletes a child profile
  - `DELETE /privacy/wipe` — wipes all demo data
- Configurable `RETENTION_DAYS`. A simple maintenance endpoint `POST /privacy/maintenance` prunes old logs.

### 5) Employer Benefits Edition
- **Org & SSO scaffold:** create orgs, map user emails to orgs, begin OIDC (Auth0/Azure AD/Google Workspace). Dev-friendly `MockSSO` login works out-of-the-box.
- **Analytics:** event log (`backend/data/events.jsonl`) + aggregated KPIs: `GET /admin/metrics/aggregate`.
- **Admin dashboard (lite)** at `frontend/admin.html` (token-gated).

---

## Security Notes
- Replace placeholders in `backend/config.py` (VAPID keys, OIDC secrets).
- Use HTTPS in production; configure CORS to allowed origins.
- Run a security review before any real user data.
# haven-ai-nanny-pro-starter
