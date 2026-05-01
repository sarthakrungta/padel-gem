# Deployment Guide — Padel Court Tracker (SQLite + GitHub Gist)
================================================================

## Architecture

```
Railway (poller)
  - runs playtomic_tracker.py --loop every 5 min
  - stores data in SQLite on Railway's persistent disk
  - after each poll, pushes JSON export to a secret GitHub Gist
                        |
                        v
            GitHub Gist (JSON file, ~100KB)
                        |
                        v
Streamlit Community Cloud (dashboard)
  - fetches Gist over HTTPS every 2 min
  - renders charts and tables
  - shareable public URL, no login needed
```

No external database. No DNS issues. Just SQLite + a Gist.

---

## Step 1 — Create a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name e.g. "padel-tracker"
4. Tick ONLY the "gist" scope
5. Click "Generate token" and copy it — you won't see it again

---

## Step 2 — Create the Gist (run once on your laptop)

```bash
cd your-project-folder
pip install -r requirements.txt

export GITHUB_TOKEN="ghp_your_token_here"
python db.py --init          # creates local SQLite tables
python db.py --create-gist   # creates the secret Gist
```

You'll see output like:
```
Gist created!
  GIST_ID      = abc123def456
  View URL     = https://gist.github.com/abc123def456

Set these in Railway env vars:
  GIST_ID      = abc123def456
  GITHUB_TOKEN = ghp_your_token_here

Set this in Streamlit secrets:
  GIST_RAW_URL = "https://gist.githubusercontent.com/YOU/abc123def456/raw/padel_tracker_data.json"
```

Save all three values.

---

## Step 3 — Deploy to Railway (poller)

1. Push all files to a GitHub repo
2. Go to https://railway.app → New Project → Deploy from GitHub repo
3. Select your repo
4. Go to your service → Variables tab → add:
   ```
   GITHUB_TOKEN = ghp_your_token_here
   GIST_ID      = abc123def456
   ```
5. Railway will auto-run: `python playtomic_tracker.py --loop`
   (as configured in railway.toml)
6. Check Logs tab — you should see polls firing every 5 minutes

Note: Railway Hobby plan is $5/month for always-on service.
Free tier sleeps after inactivity which will break the polling loop.

---

## Step 4 — Deploy to Streamlit (dashboard)

1. Go to https://share.streamlit.io → New app
2. Select your GitHub repo, branch: main, file: dashboard.py
3. Click "Advanced settings" → Secrets, paste:
   ```toml
   GIST_RAW_URL = "https://gist.githubusercontent.com/YOU/abc123def456/raw/padel_tracker_data.json"
   ```
4. Click Deploy

Your dashboard will be live at a URL like:
  https://yourname-padel-tracker-dashboard-xyz.streamlit.app

Share that link with anyone — no login required.

---

## File structure

```
padel_tracker/
├── db.py                  # SQLite layer + Gist export
├── playtomic_tracker.py   # poller (runs on Railway)
├── dashboard.py           # Streamlit dashboard
├── requirements.txt       # Python deps (no psycopg2 needed)
├── railway.toml           # Railway config
└── DEPLOY.md              # this file
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Dashboard shows "No data yet" | Check Railway logs — poller might be crashing |
| Gist export fails | Check GITHUB_TOKEN and GIST_ID are set in Railway vars |
| Dashboard can't load Gist | Check GIST_RAW_URL in Streamlit secrets — must be the /raw/ URL |
| SQLite errors on Railway | Add DB_PATH=/data/padel.db to Railway vars and enable persistent disk |
