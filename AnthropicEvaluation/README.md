# Anthropic Computer Use Evaluation (Concise)

Runs Claude's Computer Use agent headful under Playwright/Chrome and normalizes outputs to the shared schema used by Notte/Browser Use.

## What it does
- Calls Anthropic Messages API with the computer tool and executes low-level UI actions via Playwright (click, move, hover, scroll, key, type, screenshot).
- Saves a post‑action screenshot per step; writes local `result.json` and compressed `result.zst`; optionally uploads artifacts to GCS.

## Model and tool
- Default tool: `computer_20250124` with beta header `computer-use-2025-01-24`.
- Default model is taken from `--model` (e.g., `claude-sonnet-4-20250514`).

## URL handling (current)
- Start URL precedence: `START_URL` env → first explicit URL in the task → LLM-picked homepage → fallback `https://www.google.com/`.
- A screenshot is captured after pre‑navigation and included in the initial request so the model “sees” the page.
- The agent supports an `open_url` action and exposes it as a tool so Claude can request navigation directly.

## Build
```bash
# Build neurosim-base once (amd64)
cd /Users/anaishowland/Documents/agent-hub-v0.1.2
TOKEN=$(gcloud auth application-default print-access-token)
docker buildx build --platform linux/amd64 --load \
  --build-arg GCLOUD_ACCESS_TOKEN="$TOKEN" \
  -t neurosim-base \
  -f Dockerfile.base .

# Build Anthropic agent from repo root (uses local neurosim-base)
cd /Users/anaishowland/Documents/agent-hub
docker build -t anthropic-eval:local-amd64 -f AnthropicEvaluation/Dockerfile .
```

## Run locally (headful)
```bash
# Uses .env for ANTHROPIC_API_KEY and optional BUCKET_NAME/Redis
docker run --pull=never -it --rm --platform linux/amd64 \
  --env-file /Users/anaishowland/Documents/agent-hub/.env \
  -e LOG_LEVEL=DEBUG \
  -e GOOGLE_CLOUD_PROJECT=evaluation-deployment \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
  -v $HOME/.config/gcloud/application_default_credentials.json:/root/.config/gcloud/application_default_credentials.json:ro \
  -v /Users/anaishowland/Documents/agent-hub:/app -w /app \
  anthropic-eval:local-amd64 \
  --jobId anthropic/local \
  --task "Check the current stock price for Apple (AAPL) on a financial news website." \
  --taskId finance1 \
  --user anais \
  --episode 0 \
  --model claude-sonnet-4-20250514 \
  --advanced_settings '{"max_steps":5,"temperature":0}'
```

Notes
- Keep `HEADLESS=0` for desktop screenshots. Tool display is set to 1280×720; the browser viewport is 1280×1080.
- Artifacts are written under `<JOB_ID>/<EPISODE>/<TASK_ID>/` as `result.json`, `result.zst`, and `screenshot_*.png`.
- When `BUCKET_NAME` is set, artifacts upload to `gs://{BUCKET_NAME}/{USER_ID}/{JOB_ID}/{EPISODE}/{TASK_ID}/`.

## References
- Anthropic docs (computer use): `https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool`
- Anthropic quickstart (computer-use-demo): `https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo`
