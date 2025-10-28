# Dockerfile for OpenAI Computer Use (built atop neurosim-base)
FROM neurosim-base:latest

ENV PYTHONUNBUFFERED=1 \
  PLAYWRIGHT_BROWSERS_PATH=0

# System libraries needed for Chrome/Playwright (mirror Browser Use)
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

# Install Playwright
RUN uv pip install --system playwright
# Install Playwright browsers (system deps are already present above)
RUN python -m playwright install chrome
# Copy only requirements first (build context is OpenaiEvaluation/)
COPY requirements.txt /app/OpenaiEvaluation/requirements.txt
WORKDIR /app

# Install Python deps for OpenAI CUA
RUN uv pip install --system -r /app/OpenaiEvaluation/requirements.txt

# Copy application code
COPY . /app/OpenaiEvaluation

# Run under Xvfb, call the unified module
# COPY ./OpenaiEvaluation/entry.sh /usr/local/bin/openai-entry.sh
RUN chmod +x ./OpenaiEvaluation/entry.sh
ENTRYPOINT ["./OpenaiEvaluation/entry.sh"]

