# GlpiLeveling

Turn your GLPI helpdesk into a medieval RPG for your technicians.  
Every closed ticket earns XP, levels up your character and unlocks equipment, badges and PvP fights.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quick Start (Docker)](#quick-start-docker)
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
| **Leaderboard** | Technician ranking by XP / level |
| **Worker** | Automatic GLPI sync — awards XP and badges on every closed ticket |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Docker Compose                 │
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   app    │  │  worker  │  │  ollama  │  │
│  │Streamlit │  │GLPI sync │  │   LLM    │  │
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

- **app** — Streamlit web interface, accessible on your internal network
- **worker** — polls GLPI every N seconds, processes closed tickets via LLM, awards XP
- **ollama** — local LLM (mistral) to score ticket difficulty and compliance
- **db** — PostgreSQL, stores players, equipment, combats, expeditions, badges
- **GLPI** — your existing instance, untouched

---

## Requirements

- **Docker** >= 24 and **Docker Compose** >= 2.20
- Network access to your GLPI instance (REST API enabled)
- ~4 GB of available RAM on the server (mainly for Ollama + mistral)
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

Required variables:

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL password (choose a strong password) |
| `DATABASE_URL` | Replace `changez_moi` with the same password as above |
| `GLPI_API_BASE_URL` | GLPI REST API URL, e.g. `https://glpi.company.com/api.php` |
| `GLPI_OAUTH_CLIENT_ID` | OAuth2 client created in GLPI (see next section) |
| `GLPI_OAUTH_CLIENT_SECRET` | OAuth2 client secret |
| `GLPI_BOT_USERNAME` | Bot account username in GLPI |
| `GLPI_BOT_PASSWORD` | Bot account password |

### 3. Launch

```bash
bash start.sh
```

The script will:
1. Start the database and Ollama
2. Download the mistral model (first time only, ~4 GB)
3. Start the app and the worker

The interface is available at `http://SERVER_IP:8501`.

### Useful commands

```bash
# Stream all logs
docker compose logs -f

# Logs for a specific service
docker compose logs -f worker

# Stop all services
docker compose down

# Stop and delete all data
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
| Python code (`app/`, `sync/`) | `git pull && docker compose up -d --build app worker` |
| New package (`requirements.txt`) | `git pull && docker compose up -d --build app worker` |
| Environment variables (`.env`) | `docker compose restart app worker` |
| `docker-compose.yml` only | `docker compose up -d` |

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

### Logging into the app

Technicians log in with their regular GLPI credentials — no separate account needed.

---

## Local Development

Without Docker, to develop on Windows:

```powershell
# Install dependencies
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Start the app
streamlit run app/Aventurier.py --server.port 8501

# Start the worker (in a separate terminal)
cd sync
python worker.py
```

Additional requirements: a local PostgreSQL instance and Ollama installed separately.

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
- Upgrades +1 to +20: cost = `tier_price × level × 0.6`

### Expedition (2h)

- 3 weighted rolls per expedition (Gold 38%, Wood 28%, Iron Ore 20%, Runic Crystal 10%, Void Essence 4%)
- Pity system: guarantees a Void Essence after 10 expeditions without obtaining one

### PvP Arena

- Turn-based combat with optional gold bets
- Dodge chance based on defender's Agility vs attacker's Strength
- 3 attack types with speed penalties (Quick 0%, Heavy -20%, Critical -40%)
