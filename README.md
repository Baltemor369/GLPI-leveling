# GlpiLeveling

Turn your GLPI helpdesk into a medieval RPG for your technicians.  
Every closed ticket earns XP, levels up your character and unlocks equipment, badges and PvP fights.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quick Start (Docker)](#quick-start-docker)
- [Environment Variables](#environment-variables)
- [GLPI Configuration](#glpi-configuration)
- [Local Development](#local-development)
- [Game Mechanics](#game-mechanics)

---

## Features

| Module | Description |
|---|---|
| **Adventurer** | RPG profile per technician — XP, level, stats (Strength / Constitution / Agility / Spirit) |
| **Forge** | 15 items across 5 tiers (weapons, armors, amulets) with passives and upgrades +1→+20 |
| **Arena** | Turn-based PvP combat with dodge, passives and gold betting |
| **Expedition** | 2-hour mission with weighted loot (3 rolls per expedition, pity guaranteed at 10 runs) |
| **Badges** | 20 unlockable achievements (tickets, combat, forge, levels) |
| **Leaderboard** | Technician ranking by XP / level / combat wins |
| **Worker** | Automatic GLPI sync — awards XP and badges on every closed ticket |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                 │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   app    │  │  worker  │  │  ollama  │  │
│  │  Flask   │  │GLPI sync │  │   LLM    │  │
│  │ :8501    │  │ (loop)   │  │ :11434   │  │
│  └────┬─────┘  └────┬─────┘  └──────────┘  │
│       └─────────────┴──────────┐            │
│                          ┌─────┴──────┐     │
│                          │ PostgreSQL │     │
│                          │    db      │     │
│                          └────────────┘     │
└─────────────────────────────────────────────┘
                     │
              ┌──────┴──────┐
              │ GLPI (ext.) │   your existing instance
              └─────────────┘
```

The project is split into two fully independent layers that share only the PostgreSQL database:

| Layer | Directory | Role |
|---|---|---|
| **Frontend** | `web/` | Flask 3 + Jinja2 + HTMX web interface served by Gunicorn |
| **Backend** | `sync/` | Worker that polls GLPI, scores tickets via LLM, awards XP and badges |

### `web/` — Flask frontend

```
web/
├── app.py              # Flask application factory (create_app)
├── auth.py             # GLPI OAuth2 login + login_required decorator
├── queries.py          # Read/write DB layer used by all blueprints
├── routes/
│   ├── auth.py         # /login, /logout
│   ├── aventurier.py   # / (profile, stat allocation)
│   ├── classement.py   # /classement
│   ├── journal.py      # /journal (ticket history)
│   ├── forge.py        # /forge (buy, equip, upgrade items)
│   ├── arene.py        # /arene (PvP lobby, combat, HTMX polling)
│   ├── expedition.py   # /expedition (launch, loot, HTMX polling)
│   └── badges.py       # /badges
├── templates/          # Jinja2 templates (base.html + per-page)
│   ├── base.html
│   ├── partials/       # HTMX partial responses (combat, expedition, wait-room)
│   └── arene/
└── static/css/
    └── style.css       # Dark-fantasy CSS theme
```

Each route module is a standalone Blueprint with no shared Streamlit-style state.  
HTMX polling (combat 2 s, wait-room 3 s, expedition 30 s) stops automatically when the
target `<div>` is replaced by Gunicorn's HTTP 286 response.

### `sync/` — GLPI synchronisation worker

```
sync/
├── worker.py           # Main polling loop (SYNC_INTERVAL_SECONDS)
├── glpi_client.py      # GLPI REST API wrapper
├── xp_engine.py        # XP formula (category × urgency × impact × difficulty × speed)
├── badge_engine.py     # Badge unlock logic
├── combat_engine.py    # Turn-based PvP resolution
├── ollama_client.py    # LLM difficulty / compliance scoring
├── db.py               # DB helpers shared by worker and blueprints
└── config.py           # Env-var loading (imported by both layers)
```

---

## Requirements

- **Docker** >= 24 and **Docker Compose** >= 2.20
- Network access to your GLPI instance (REST API enabled)
- ~4 GB of available RAM (mainly for Ollama + mistral)
- ~5 GB of disk space (Ollama image + mistral model ~4 GB)

---

## Quick Start (Docker)

### 1. Clone the repository

```bash
git clone https://github.com/Baltemor369/GLPI-leveling.git
cd GLPI-leveling
```

### 2. Configure the environment

```bash
cp .env.example .env
nano .env   # or vim, notepad, etc.
```

See [Environment Variables](#environment-variables) for a full description of each variable.

### 3. Launch

```bash
docker compose up -d --build
```

The interface is available at `http://SERVER_IP:8501`.

Technicians log in with their regular GLPI credentials — no separate account needed.

### Useful commands

```bash
# Stream all logs
docker compose logs -f

# Logs for a specific service
docker compose logs -f worker

# Stop all services
docker compose down

# Stop and delete all data (including the database)
docker compose down -v
```

### Updates & patches

After pulling new code:

```bash
git pull
docker compose up -d --build app worker
```

The `--build` flag only rebuilds the application image. The database and Ollama are **not** affected — their data lives in persistent volumes.

| What changed | Command |
|---|---|
| Python code (`web/`, `sync/`) | `git pull && docker compose up -d --build app worker` |
| New package (`requirements.txt`) | `git pull && docker compose up -d --build app worker` |
| Environment variables (`.env`) | `docker compose restart app worker` |
| `docker-compose.yml` only | `docker compose up -d` |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in every value before starting.

### PostgreSQL

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Database password (choose a strong value) |
| `DATABASE_URL` | Full connection string — replace `changez_moi` with the same password |

### GLPI

| Variable | Description |
|---|---|
| `GLPI_API_BASE_URL` | GLPI REST API URL, ending with `/api.php` |
| `GLPI_OAUTH_CLIENT_ID` | OAuth2 client ID (see [GLPI Configuration](#glpi-configuration)) |
| `GLPI_OAUTH_CLIENT_SECRET` | OAuth2 client secret |
| `GLPI_BOT_USERNAME` | Bot account username used by the worker |
| `GLPI_BOT_PASSWORD` | Bot account password |

### Application

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(required)* | Flask session signing key — use a long random string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `APP_PORT` | `8501` | Host port exposed by the `app` container |
| `TZ` | `Europe/Paris` | Server timezone used for timestamp display |

### Synchronisation / LLM

| Variable | Default | Description |
|---|---|---|
| `SYNC_INTERVAL_SECONDS` | `60` | Seconds between GLPI polling cycles |
| `OLLAMA_API_URL` | `http://ollama:11434` | Ollama endpoint (change if running Ollama externally) |
| `OLLAMA_MODEL` | `mistral` | LLM model used for ticket scoring |

---

## GLPI Configuration

### Create an OAuth2 client

1. In GLPI: **Setup → OAuth 2.0 → Add a client**
2. Name: `GlpiLeveling`
3. Enable the `Resource Owner Password` grant type
4. Copy the generated `client_id` and `client_secret` into your `.env`

### Create a bot account

1. **Administration → Users → Add**
2. Name: `bot-glpileveling` (or any name)
3. Minimum required rights: read access on tickets and users
4. Set `GLPI_BOT_USERNAME` and `GLPI_BOT_PASSWORD` in your `.env`

---

## Local Development

Without Docker, to develop on Windows:

```powershell
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set required environment variables (minimum viable set)
$env:SECRET_KEY        = "dev-secret-key"
$env:DATABASE_URL      = "postgresql://glpi:password@localhost:5432/glpileveling"
$env:GLPI_API_BASE_URL = "https://glpi.company.com/api.php"
$env:GLPI_OAUTH_CLIENT_ID     = "your-client-id"
$env:GLPI_OAUTH_CLIENT_SECRET = "your-client-secret"

# Start the Flask app (development server)
python -m flask --app web.app run --port 8501

# Start the worker in a separate terminal
python sync/worker.py
```

Additional requirements: a local PostgreSQL instance and Ollama installed separately.

`PYTHONPATH` must include both the project root (for `web.*` imports) and `sync/` (for `config`,
`db`, `badge_engine`, etc. imported by the blueprints). In Docker this is set via `ENV PYTHONPATH=/app/sync:/app`.

---

## Game Mechanics

### XP per ticket

```
XP = category_base × urgency_coeff × impact_coeff × difficulty_coeff × speed_coeff
```

| Parameter | Value |
|---|---|
| Server category base | 5 XP |
| Workstation category base | 3 XP |
| WiFi / Peripheral base | 2 XP |
| High urgency (≥ 4) | × 1.2 |
| High impact (≥ 4) | × 1.2 |
| LLM difficulty (1–10) | × (1 + score/10) |
| Same-day resolution | × 1.5 |
| Resolution after 5+ days | × 1.0 (floor) |

The technician who created the ticket also receives **compliance XP** based on the quality of the ticket fields (title, description, contact info) as evaluated by the LLM.

### Leveling up

Each level grants **3 stat points** to freely distribute across Strength, Constitution, Agility and Spirit.

### Forge

- 15 items across 5 tiers (Iron → Steel → Mithril → Runic → Void)
- Tiers 3–5 require materials obtained from expeditions
- Upgrades +1 to +20: cost = `tier_price × (level + 1) × 0.6` (−30% if Oak Wood is in stock)

### Expedition (2h)

- 3 weighted rolls per expedition (Gold 38%, Wood 28%, Iron Ore 20%, Runic Crystal 10%, Void Essence 4%)
- Pity system: guarantees a Void Essence after 10 expeditions without obtaining one

### PvP Arena

- Turn-based combat with optional gold bets
- Dodge chance based on defender's Agility vs attacker's Strength
- 3 attack types with speed penalties (Quick 0%, Heavy −20%, Critical −40%)
- Combat Elo points (`points_combat`) track competitive standing independently of XP
