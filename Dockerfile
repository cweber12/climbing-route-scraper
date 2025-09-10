FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        unzip \
        chromium-driver \
        chromium && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for Chrome/Chromium
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Default command (can be changed as needed)
ENTRYPOINT ["python", "scrape_routes.py"]