# Deployment Guide — Padel Court Tracker
=========================================

## Architecture

```
GitHub repo (your code)
    ↓
Railway.app  ──── runs playtomic_tracker.py --loop every 5 min
    ↓  writes to
Supabase ──── PostgreSQL database (free tier)
    ↑  reads from
Streamlit Cloud ──── public dashboard URL (free)
```

---

## Step 1 — Supabase (database)

1. Go to https://supabase.com and create a free account
2. Click "New Project", give it a name (e.g. "padel-tracker"), pick a region
   closest to Australia (ap-southeast-2 Sydney)
3. Once created, go to: Project Settings → Database → Connection string
4. Select **URI** mode and copy the string. It looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres`
5. Keep this safe — you'll need it in steps 2 and 3.

**Create the tables (one-time setup):**
```bash
# On your laptop, in the project folder:
pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:..."   # paste your URI
python db.py --init
```
You should see: "Schema initialised (or already exists)."

---

## Step 2 — Railway (poller)

1. Go to https://railway.app and sign up (GitHub login is easiest)
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub account and select the repo with these files
4. Railway will detect the `railway.toml` and start deploying
5. Once deployed, go to your service → **Variables** tab
6. Add one environment variable:
   ```
   DATABASE_URL = postgresql://postgres:...   (your Supabase URI from Step 1)
   ```
7. Railway will restart the service. Check the **Logs** tab — you should see:
   ```
   Continuous mode — polling every 300s...
   [2026-05-01 08:00:00 AEST] ── Poll starting for 2026-05-01
     Fetching API for 2026-05-01 …
     Courts found: 3
     ✓ DB updated. Poll complete.
   ```

**Cost:** Free tier gives 500 hours/month. This service runs 24/7 = ~720h/month.
Upgrade to Hobby plan ($5/month) to run without sleep.

---

## Step 3 — Streamlit Community Cloud (dashboard)

1. Push all files to a GitHub repo (public or private)
2. Go to https://share.streamlit.io and sign in with GitHub
3. Click "New app"
4. Select your repo, branch (main), and set:
   - Main file path: `dashboard.py`
5. Click "Advanced settings" → Secrets
6. Add your database URL in TOML format:
   ```toml
   DATABASE_URL = "postgresql://postgres:..."
   ```
7. Click "Deploy"

Your dashboard will be live at a URL like:
`https://yourname-padel-tracker-dashboard-abc123.streamlit.app`

Share this link with anyone — no login needed.

---

## Step 4 — Update court names (optional but recommended)

In `dashboard.py`, find the `COURT_LABELS` dict near the top and
replace the UUIDs with friendly names:

```python
COURT_LABELS = {
    "4a5fb5fe-139f-40b0-85e7-634c705d7284": "Court 1",
    "6a01f11b-3f57-4e81-bf0d-c1359d82caef": "Court 2",
    "e60b3a03-4c04-4021-a531-626d7d973135": "Court 3",
}
```

---

## File structure

```
padel_tracker/
├── db.py                  # database read/write layer (Supabase)
├── playtomic_tracker.py   # poller — runs on Railway
├── dashboard.py           # Streamlit dashboard
├── requirements.txt       # Python dependencies
├── railway.toml           # Railway deployment config
└── DEPLOY.md              # this file
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `EnvironmentError: DATABASE_URL not set` | Set the env var in Railway / Streamlit secrets |
| `SSL error` on DB connect | Make sure URI has `?sslmode=require` at the end |
| Dashboard shows "No data yet" | Check Railway logs — poller might be failing |
| Slots all show "unknown" | Poller ran but `db.py --init` was never run |
| Wrong court names | Update `COURT_LABELS` in `dashboard.py` |
