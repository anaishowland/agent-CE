# Dockerfile for Notte Evaluation
FROM neurosim-base

ENV PYTHONUNBUFFERED=1 \
    GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    fonts-liberation \
    libappindicator3-1 \
    libcurl4 \
    libpci3 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install --system browser-use playwright
# Install Playwright browser
RUN uv run playwright install chrome

# Copy application code
COPY . /app/BrowseruseEvaluation
WORKDIR /app

RUN chmod +x ./BrowseruseEvaluation/entry.sh

ENTRYPOINT ["./BrowseruseEvaluation/entry.sh"]