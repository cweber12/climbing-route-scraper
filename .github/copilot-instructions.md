# Copilot Instructions

## Project Structure

Monorepo with two services:
- `api/` — FastAPI service deployed to Render (no Chromium, DB read/write only)
- `scraper/` — Selenium crawler, runs locally via Docker; calls `api/` write endpoints when `API_URL` is set
- `tests/` — shared pytest suite; `pytest.ini` adds both `api` and `scraper` to `pythonpath`

Each service has its own `Dockerfile` and `requirements.txt`. Root `requirements.txt` is CI-only.

## Architecture

```
local Docker (scraper/) ──PUT──▶ Render API (api/) ──▶ Neon PostgreSQL
external apps           ──GET──▶ Render API (api/)
```

- `API_URL` unset → scraper writes directly to DB via `DatabaseWriter`
- `API_URL` set   → scraper calls Render PUT endpoints via `ApiWriter` (api_client.py)

## Build & Test

```bash
pytest tests/ -v                              # run test suite from project root
docker-compose build scraper                  # (re)build local scraper image after scraper/ changes
docker-compose run --rm scraper python scrape_routes.py <URL>   # run scraper
docker-compose up db                          # start local PostgreSQL only
```

## Conventions

- PostgreSQL: `ON CONFLICT ... DO UPDATE SET` for all upserts; never `INSERT OR IGNORE`
- Schema managed by `api/create_schema.py`; `reset=False` by default (non-destructive)
- Neon `DATABASE_URL` credential lives only on Render — never in the local scraper image
- `api_client.py` re-uses a single `httpx.Client` across the crawl session (connection pooling)
- Use `RealDictCursor` (from `route_db_connect.py`) so rows are returned as dicts, not tuples

## Git Workflow

After completing any set of changes:
1. If any file under `scraper/` was modified, run `docker-compose build scraper` to rebuild the local image.
2. Stage all modified files: `git add -A`
3. Generate a [Conventional Commits](https://www.conventionalcommits.org/) message:
   - `feat:` new capability, `fix:` bug fix, `refactor:` structural change, `chore:` config/tooling
   - Body lines summarise each changed file or logical group (max ~72 chars per line)
4. Commit and push immediately: `git commit -m "<subject>" -m "<body>"` then `git push`

Do this automatically after every task without waiting to be asked.
