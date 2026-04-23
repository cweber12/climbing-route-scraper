# Climbing Route Scraper

[![CI](https://github.com/cweber12/climbing-route-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/cweber12/climbing-route-scraper/actions/workflows/ci.yml)
[![Docker](https://github.com/cweber12/climbing-route-scraper/actions/workflows/docker.yml/badge.svg)](https://github.com/cweber12/climbing-route-scraper/actions/workflows/docker.yml)

A two-part system for collecting and serving climbing data from [Mountain Project](https://www.mountainproject.com):

1. **Scraper** — a Docker container you run locally. Feed it any Mountain Project URL and it crawls the full hierarchy (parent areas + all child areas/routes) and writes everything to a PostgreSQL database.
2. **API** — a lightweight FastAPI service hosted for free on [Render](https://render.com), backed by a free [Neon](https://neon.tech) PostgreSQL database. Query areas and routes over HTTP.

---

## Table of Contents

- [Climbing Route Scraper](#climbing-route-scraper)
  - [Table of Contents](#table-of-contents)
  - [Architecture](#architecture)
  - [API Reference](#api-reference)
    - [Operations](#operations)
    - [Scraper](#scraper)
    - [Data Query](#data-query)
  - [Database Schema](#database-schema)
  - [Quick Start — Local Scraping](#quick-start--local-scraping)
  - [Environment Variables](#environment-variables)
  - [Running Tests](#running-tests)
  - [CI/CD](#cicd)
  - [Hosting Guide — Free Tier Stack](#hosting-guide--free-tier-stack)
    - [Database: Neon (PostgreSQL, free forever)](#database-neon-postgresql-free-forever)
    - [API: Render (free tier)](#api-render-free-tier)
    - [Workflow Summary](#workflow-summary)

---

## Architecture

```
┌─────────────────── Local Machine ───────────────────────┐
│                                                          │
│  docker run ... climbing-route-scraper <MP_URL>         │
│       │                                                  │
│  Dockerfile (Chromium + Selenium + BS4)                 │
│       │                                                  │
│  crawl_area() ──► scrape_routes.py                      │
│                                                          │
└──────────────────────┬───────────────────────────────────┘
                       │ psycopg2 / DATABASE_URL
                       ▼
         ┌─────────────────────────┐
         │  Neon PostgreSQL (free) │  ◄── shared between scraper
         └────────────┬────────────┘       and hosted API
                      │
         ┌────────────▼────────────┐
         │  Render (free tier)     │
         │  FastAPI  api.py        │
         │  Dockerfile.api         │
         │  GET /areas             │
         │  GET /routes            │
         └─────────────────────────┘
```

---

## API Reference

All endpoints are served on port `8000`.  
Interactive docs: `http://localhost:8000/docs` (local) or `https://<your-render-app>.onrender.com/docs` (hosted).

### Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/setup` | Initialise DB schema (`?reset=true` to drop first) |

### Scraper

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/scrape` | Submit a crawl job; returns a `task_id` |
| `GET` | `/status/{task_id}` | Poll job status: `queued` → `running` → `complete`/`failed` |

### Data Query

| Method | Path | Query params | Description |
|--------|------|-------------|-------------|
| `GET` | `/areas` | `level`, `parent_id`, `q`, `limit` | List/search all areas |
| `GET` | `/areas/{area_id}` | — | Fetch a single area |
| `GET` | `/areas/{area_id}/routes` | — | All routes under an area |
| `GET` | `/routes` | `parent_id`, `rating`, `q`, `limit` | List/search routes |
| `GET` | `/routes/{route_id}` | — | Fetch a single route |

**Example — search routes by name:**
```bash
curl "https://<your-app>.onrender.com/routes?q=nose&limit=10"
```

**Example — submit a local crawl:**
```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.mountainproject.com/area/105792216/nevermind-wall"}'
# returns {"task_id": "a1b2c3d4-...", "status": "queued"}

curl http://localhost:8000/status/a1b2c3d4-...
# {"task_id": "...", "status": "complete", "message": "Scraping finished successfully."}
```

---

## Database Schema

PostgreSQL — no spatial extensions required; coordinates stored as plain `DOUBLE PRECISION` columns.

```
State
  state_id   BIGINT PK
  state      VARCHAR(255)

SubLocationsLv1 … SubLocationsLv10
  location_id    BIGINT PK
  location_name  VARCHAR(255)
  parent_id      BIGINT
  latitude       DOUBLE PRECISION
  longitude      DOUBLE PRECISION

Routes
  route_id    BIGINT PK
  route_name  VARCHAR(255)
  parent_id   BIGINT
  rating      VARCHAR(50)

VIEW all_areas   ← unions State + all SubLocationsLv* for easy querying
  area_id, area_name, level, parent_id, latitude, longitude
```

Hierarchy mirrors Mountain Project:

```
State (level 0)
  └─ Region (level 1)
       └─ Crag (level 2)
            └─ Wall (level 3+)
                 └─ Routes
```

---

## Quick Start — Local Scraping

**Prerequisites:** Docker Desktop.

**1. Clone and configure:**

```bash
git clone https://github.com/cweber12/climbing-route-scraper.git
cd climbing-route-scraper
cp .env.example .env
```

Edit `.env` — set `DATABASE_URL` to your Neon connection string (see [Hosting Guide](#hosting-guide--free-tier-stack)), or use the individual `DB_*` vars to point at a local PostgreSQL instance.

**2. Start the full local stack (PostgreSQL + API):**

```bash
docker compose up --build
```

**3. Initialise the schema:**

```bash
curl -X POST http://localhost:8000/setup
```

**4. Run a crawl:**

```bash
# Via API (background job)
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.mountainproject.com/area/105792216/nevermind-wall"}'

# Or directly via Docker CLI (foreground, logs to stdout)
docker run --env-file .env climbing-route-scraper \
  python scrape_routes.py "https://www.mountainproject.com/area/105792216/nevermind-wall"
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Preferred | — | Full PostgreSQL connection string (e.g. from Neon). Overrides all `DB_*` vars. |
| `DB_HOST` | If no `DATABASE_URL` | — | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_USER` | If no `DATABASE_URL` | — | PostgreSQL username |
| `DB_PASSWORD` | If no `DATABASE_URL` | — | PostgreSQL password |
| `DB_NAME` | No | `routes_db` | Database name |

Copy `.env.example` to `.env`. **Never commit `.env` to source control.**

---

## Running Tests

No live database or browser required — all external interactions are mocked.

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Coverage includes HTML parsing, DB insertion logic, crawl lifecycle (driver/connection management, URL deduplication), and all API endpoints.

---

## CI/CD

| Workflow | Trigger | Action |
|----------|---------|--------|
| `ci.yml` | Push / PR to `main` | `pytest` + `ruff` lint |
| `docker.yml` | Push to `main` or `v*.*.*` tag | Build + push to `ghcr.io/cweber12/climbing-route-scraper` |

---

## Hosting Guide — Free Tier Stack

### Database: Neon (PostgreSQL, free forever)

Neon is a serverless PostgreSQL provider with a genuinely free tier (no credit card, no expiry). PostgreSQL is the most widely used open-source database (Stack Overflow 2024 survey: #1 for three consecutive years).

1. Sign up at [neon.tech](https://neon.tech) — no credit card required.
2. Create a project → create a database named `routes_db`.
3. Copy the **connection string** from the Neon dashboard — it looks like:
   ```
   postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/routes_db?sslmode=require
   ```
4. Set this as `DATABASE_URL` in your `.env` (local scraper) and in Render's environment variables (hosted API).

**Free tier limits:** 0.5 GB storage, compute auto-suspends after 5 minutes of inactivity (resumes on next query in ~500 ms).

---

### API: Render (free tier)

Render's free web service tier auto-deploys from GitHub, supports Docker, and includes TLS. The `Dockerfile.api` image is lean (no Chromium) so it builds in under a minute.

**One-time setup:**

1. Push your repo to `https://github.com/cweber12/climbing-route-scraper`.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your GitHub repo.
3. Render will detect `render.yaml` automatically and configure the service.
4. In the Render dashboard → **Environment** → add:
   ```
   DATABASE_URL = postgresql://...  (your Neon connection string)
   ```
5. Click **Deploy**. Your API will be live at `https://<app-name>.onrender.com`.
6. Initialise the schema once:
   ```bash
   curl -X POST https://<app-name>.onrender.com/setup
   ```

**Free tier limits:** 750 hours/month (enough for one always-on service), service sleeps after 15 minutes of inactivity and wakes on the next request (~30 s cold start).

---

### Workflow Summary

```
┌─────────────────────────────────────────────────────┐
│  1. Run scraper locally (Docker)                    │
│     docker run --env-file .env <image>              │
│       python scrape_routes.py <MP_URL>              │
│                    │                                │
│                    │ writes via DATABASE_URL         │
│                    ▼                                │
│          Neon PostgreSQL (free)                     │
│                    │                                │
│                    │ reads via DATABASE_URL          │
│                    ▼                                │
│  2. Query via hosted API (Render free tier)         │
│     GET https://<app>.onrender.com/routes?q=nose    │
└─────────────────────────────────────────────────────┘
```

