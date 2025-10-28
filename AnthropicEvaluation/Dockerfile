# syntax=docker/dockerfile:1
# Use the shared neurosim-base for parity with other agents
FROM neurosim-base:latest

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_BROWSERS_PATH=0 \
    XDG_RUNTIME_DIR=/tmp/xdg

ENV PLAYWRIGHT_BROWSERS_PATH=0

WORKDIR /app

# System libraries needed for Chrome/Playwright (mirror OpenAI image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libicu-dev \
    libjpeg62-turbo \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libvpx-dev \
    libwebp-dev \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    lsb-release \
    wget \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (build context is AnthropicEvaluation/)
COPY requirements.txt /app/AnthropicEvaluation/requirements.txt
# Runtime deps for AnthropicEvaluation (Playwright already present in base)
RUN python -m pip install --no-cache-dir -r /app/AnthropicEvaluation/requirements.txt \
    && python -m playwright install chrome

# Copy application code (build context scoped to AnthropicEvaluation/)
COPY . /app/AnthropicEvaluation

# Ensure entrypoint script is executable
RUN chmod +x /app/AnthropicEvaluation/entry.sh

# Default entrypoint: use the wrapper script (prints early diagnostics) under Xvfb
ENTRYPOINT ["/app/AnthropicEvaluation/entry.sh"]
