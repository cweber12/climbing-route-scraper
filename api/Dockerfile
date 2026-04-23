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

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
