# Climbing Route Scraper

[![Pipeline](https://github.com/cweber12/climbing-route-scraper/actions/workflows/pipeline.yml/badge.svg)](https://github.com/cweber12/climbing-route-scraper/actions/workflows/pipeline.yml)

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
    - [Local-Only Mode (no Render)](#local-only-mode-no-render)
  - [Environment Variables](#environment-variables)
  - [Running Tests](#running-tests)
  - [CI/CD](#cicd)
  - [Hosting Guide — Free Tier Stack](#hosting-guide--free-tier-stack)
    - [Database: Neon (PostgreSQL, free forever)](#database-neon-postgresql-free-forever)
    - [API: Render (free tier)](#api-render-free-tier)
    - [Workflow Summary](#workflow-summary)

---

## Architecture

The system has two write modes, controlled by the `API_URL` environment variable:

```
┌─────────────────────── Local Machine ──────────────────────────┐
│                                                                 │
│  docker-compose run --rm scraper python scrape_routes.py <URL> │
│       │                                                         │
│  scraper/Dockerfile  (Chromium + Selenium + BS4)               │
│       │                                                         │
│  crawl_area()  →  ApiWriter  (API_URL set — recommended)       │
│       │           or                                            │
│       │           DatabaseWriter  (API_URL unset — local only) │
│       │                                                         │
└───────┼─────────────────────────────────────────────────────────┘
        │ HTTP PUT                         │ psycopg2 (direct)
        ▼                                  ▼
┌───────────────────┐           ┌──────────────────────┐
│  Render (free)    │           │  local PostgreSQL     │
│  FastAPI api.py   │──────────►│  (docker-compose db)  │
│  PUT /areas       │ psycopg2  └──────────────────────┘
│  PUT /areas/routes│
│  GET /areas       │
│  GET /routes      │
└────────┬──────────┘
         │ psycopg2
         ▼
┌──────────────────────┐
│  Neon PostgreSQL     │
│  (free, hosted)      │
└──────────────────────┘
```

**Recommended flow** (`API_URL` set in `.env`): scraper runs locally → calls `PUT` endpoints on the Render-hosted API → API writes to Neon. The local machine never needs database credentials.

**Local-only flow** (`API_URL` empty): scraper writes directly to the `db` container via `DATABASE_URL`. Useful for development without a Render deployment.

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

Edit `.env`:
- Set `API_URL` to your deployed Render service URL (e.g. `https://climbing-route-scraper-api.onrender.com`).
- Leave `DATABASE_URL` empty if using the Render/Neon path — the scraper never needs DB credentials when `API_URL` is set.

**2. Initialise the schema on Neon (one-time):**

```bash
curl -X POST https://<your-render-app>.onrender.com/setup
```

**3. Build the scraper image:**

```bash
docker-compose build scraper
```

**4. Run a crawl:**

```bash
docker-compose run --rm scraper python scrape_routes.py \
  "https://www.mountainproject.com/area/105792216/nevermind-wall"
```

The scraper connects to `API_URL`, calls `PUT /areas` and `PUT /areas/{id}/routes`, and the Render API writes everything to Neon.

---

### Local-Only Mode (no Render)

Set `API_URL=` (empty) in `.env` and provide a `DATABASE_URL` pointing at the local `db` container:

```bash
docker-compose up db          # start PostgreSQL
docker-compose run --rm scraper python scrape_routes.py <URL>
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_URL` | **Yes (recommended)** | — | URL of your deployed Render API (e.g. `https://your-app.onrender.com`). When set, the scraper sends data via HTTP PUT — no DB credentials needed locally. Leave blank to write directly to the DB. |
| `DATABASE_URL` | If no `API_URL` | — | Full PostgreSQL connection string (Neon or local). Overrides all `DB_*` vars. |
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

A single `pipeline.yml` workflow handles everything:

| Job | Trigger | Action |
|-----|---------|--------|
| `test` | Push / PR to `main` | `pytest tests/ -v --tb=short` |
| `lint` | Push / PR to `main` | `ruff check .` |
| `build-and-push` | Push to `main` or `v*.*.*` tag (after test + lint pass) | Build `api/Dockerfile` → push `ghcr.io/cweber12/climbing-route-scraper-api` → trigger Render deploy hook |

The scraper image is **never pushed to GHCR** — it is built locally only.  
Add `RENDER_DEPLOY_HOOK_URL` as a GitHub Actions secret to enable automatic Render redeploys after each push.

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

Render's free web service tier auto-deploys from GHCR, includes TLS. The `api/Dockerfile` image is lean (no Chromium) so it builds in under a minute.

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
Git push to main
  └─▶ pipeline.yml
        ├─ test (pytest)   ─┐
        ├─ lint (ruff)      ├─► both must pass
        └─ build-and-push ◄─┘
             │
             ├─ builds api/Dockerfile
             ├─ pushes ghcr.io/cweber12/climbing-route-scraper-api:main
             └─ calls RENDER_DEPLOY_HOOK_URL → Render pulls new image

Local machine
  └─▶ docker-compose run --rm scraper python scrape_routes.py <URL>
             │
             │  (API_URL set)
             └─► PUT https://<render-app>.onrender.com/areas/...
                       │
                       └─► Neon PostgreSQL (INSERT/UPDATE)

External apps
  └─▶ GET https://<render-app>.onrender.com/routes?q=...
```

