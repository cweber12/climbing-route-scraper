# scraper/Dockerfile
# ---------------------------------------------------------------------------
# Full local image with Chromium + Selenium for running the route scraper.
# NOT deployed to Render — run locally via docker-compose or docker run.
#
# Usage:
#   docker-compose run --rm scraper python scrape_routes.py <MOUNTAIN_PROJECT_URL>
# ---------------------------------------------------------------------------

FROM python:3.11-slim

# Install Chromium and its WebDriver from Debian repos
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        unzip \
        chromium-driver \
        chromium && \
    rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

RUN addgroup --system scraper && adduser --system --ingroup scraper scraper

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER scraper

# Default: run the scraper — pass the URL as a Docker argument.
# Override API_URL in .env to route writes through the hosted API instead of a local DB.
CMD ["python", "scrape_routes.py"]
