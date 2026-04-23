# api/Dockerfile
# ---------------------------------------------------------------------------
# Lean image for the FastAPI service deployed to Render.
# No Chromium — database query/write only.
# ---------------------------------------------------------------------------

FROM python:3.11-slim

RUN addgroup --system api && adduser --system --ingroup api api

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER api

EXPOSE 8000

# Render injects PORT at runtime (default 10000 on free tier).
# Fall back to 8000 for local docker-compose usage.
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
