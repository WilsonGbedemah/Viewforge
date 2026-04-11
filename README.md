# ViewForge

**YouTube Browser Automation Tool** — simulates authentic human browsing and viewing behavior using real browser automation (Playwright + Chromium). Built as a complete web application with a management dashboard.

---

## Features

- **Real browser automation** — Playwright + Chromium, one persistent profile per account
- **Human-like behavior** — curved mouse movement, micro-pauses, overshoot/correction, variable scroll speed, reverse scroll
- **Session warm-up** — home feed browse, thumbnail hover, brief video opens, channel visits before targeting
- **Watch-time controller** — weighted short/medium/long distribution, random exits, rare rewatches
- **Entry path randomization** — home feed, search results, suggested videos, channel pages, playlists, notification click
- **Engagement engine** — optional rare likes (~8%), optional rare comments (~3%) with safe phrases
- **Safety limits** — daily caps per account, forced cooldowns, automatic idle periods
- **Proxy support** — one proxy per account, HTTP and SOCKS5
- **React dashboard** — account management, proxy assignment, campaign creation, scheduling, live logs
- **WebSocket live logs** — real-time log streaming to the dashboard
- **CSV export** — export session logs for any campaign

---

## Quick Start

### Requirements

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- Make

### Setup (first time)

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Install everything (Python deps + Playwright Chromium + npm)
make install

# 3. Start the app
make dev
```

The app opens at **<http://localhost:8000>**

API docs at **<http://localhost:8000/docs>**

---

## Usage

### 1. Add Proxies

Go to **Accounts → Add Proxy**. One proxy per account is recommended.

### 2. Add Accounts

Go to **Accounts → Add Account**. Each account needs:

- A Google email address
- A browser profile (auto-created in `./profiles/`)
- Optionally: a proxy assignment and exported cookie JSON

**Cookie login:** Export cookies from a logged-in Chrome/Firefox session using a browser extension like "EditThisCookie" or "Cookie-Editor". Paste the JSON array into the account's cookie field.

### 3. Create a Campaign

Go to **Campaigns → New Campaign** and configure:

- Target YouTube URL (video, short, livestream, channel, or playlist)
- Watch time range (min/max seconds)
- Entry paths (how accounts arrive at the video)
- Assign accounts to the campaign
- Optional: enable rare likes / comments

### 4. Start the Campaign

Click **Start** on any campaign. Sessions run in the background. Monitor progress in the dashboard or via the **Logs** page.

---

## Project Structure

```text
viewforge/
├── backend/
│   ├── main.py              # FastAPI app + WebSocket
│   ├── database.py          # SQLite/SQLAlchemy setup
│   ├── models.py            # DB models
│   ├── schemas.py           # Pydantic I/O models
│   ├── routers/
│   │   ├── accounts.py      # Account CRUD
│   │   ├── proxies.py       # Proxy CRUD
│   │   ├── campaigns.py     # Campaign CRUD + start/stop
│   │   ├── logs.py          # Log query, export, clear
│   │   └── stats.py         # Dashboard stats + export
│   └── automation/
│       ├── browser.py       # Playwright profile + proxy manager
│       ├── interaction.py   # Human-like mouse/scroll/keyboard
│       ├── warmup.py        # Session warm-up routines
│       ├── watcher.py       # Watch-time + entry path controller
│       └── engine.py        # Campaign orchestrator
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, Accounts, Campaigns, Logs, Login, Signup
│       └── components/      # Sidebar, Modal, Badge, StatsCard
├── .env.example
├── Makefile
└── README.md
```

---

## Configuration (.env)

| Variable       | Default                    | Description                           |
|----------------|----------------------------|---------------------------------------|
| `HOST`         | `0.0.0.0`                  | Backend bind address                  |
| `PORT`         | `8000`                     | Backend port                          |
| `DATABASE_URL` | `sqlite:///./viewforge.db` | Database connection string            |
| `PROFILES_DIR` | `./profiles`               | Playwright persistent profile storage |
| `HEADLESS`     | `true`                     | Set `false` to see browser windows    |
| `SECRET_KEY`   | *(set in .env)*            | JWT signing secret                    |

---

## Safety Notes

- Sessions include random delays, cooldowns, and daily caps to keep behavior realistic
- Do not configure extreme session counts or zero watch-times
- The engine applies a 15–45 minute cooldown per account after each session
- Daily session counts reset automatically at midnight
- Accounts at their daily limit are skipped until the next day

---

## Tech Stack

| Layer     | Technology                   |
|-----------|------------------------------|
| Backend   | Python 3.11+, FastAPI, SQLite |
| Automation | Playwright, Chromium        |
| Scheduler | APScheduler                  |
| Frontend  | React 18, Vite, Tailwind CSS |
| Realtime  | WebSocket                    |

---

ViewForge — April 2026
