# OpenAI Computer Use Evaluation (Concise)

This module runs OpenAI's Computer Use agent headful under Playwright/Chrome and normalizes outputs to the shared schema used by Notte/Browser Use.

## What it does
- Calls `/v1/responses` (Computer Use preview) and executes suggested UI actions via Playwright.
- Saves a post‑action screenshot per step, appends normalized steps, and collects token usage when available.
- Optional: uploads per‑task `result.zst` and screenshots to GCS.

## Module layout (scripts overview)
- `main.py`: Orchestration shell matching `NotteEvaluation`/`BrowseruseEvaluation` pattern. Opens Chrome (via Playwright), resolves a sensible start URL, builds per‑step messages with focus/hover diagnostics, calls OpenAI Responses API, executes the model’s suggested action, captures screenshots, normalizes steps and tokens, writes local `result.json`, and uploads screenshots and a flat `result.zst/json` to GCS when configured.
- `llm.py`: Minimal model mapping. Returns the model name to use (defaults to `computer-use-preview`).
- `conversation.py`: Helpers to build the conversation payload each step. Adds the task text, current screenshot, mouse position, and focus/hover info; supports optional nudge system messages when the model is stuck.
- `keys.py`: Key normalization and combo handling (`Ctrl+L`, `Enter` vs `Return`, `Esc` vs `Escape`, function keys).
- `urls.py`: Start URL resolver (env → explicit URL → bare domain → Bing default).
- `operator_async.py`: Async Playwright action adapter (click/type/key/scroll/move/dblclick/screenshot/goto/back/forward/drag) with tracked mouse position. The core loop currently calls Playwright directly but this adapter is available and can be swapped in to centralize actions.

## Start URL logic (pre‑navigation)
1. `START_URL` env
2. First http(s) URL in the task
3. First bare domain normalized to `https://domain/`
4. Default: `https://www.bing.com/`

We navigate and include the first screenshot in the initial request so the model “sees” the page immediately.

## Build
```bash
# Build neurosim-base once from inside agent-hub-v0.1.2 (amd64)
cd /Users/anaishowland/Documents/agent-hub-v0.1.2
TOKEN=$(gcloud auth application-default print-access-token)
docker buildx build --platform linux/amd64 --load \
  --build-arg GCLOUD_ACCESS_TOKEN="$TOKEN" \
  -t neurosim-base \
  -f Dockerfile.base \
  .

# Build OpenAI agent from repo root (uses local neurosim-base)
cd /Users/anaishowland/Documents/agent-hub
docker build -t openai-eval:local-amd64 -f OpenaiEvaluation/Dockerfile .
# Optional: verify image arch
docker inspect openai-eval:local-amd64 --format '{{.Os}}/{{.Architecture}}'
```



## Run locally (headful)
```bash
CREDS_FILE="/Users/anaishowland/Documents/agent-hub/application_default_credentials.json"
docker run --pull=never -it --rm \
  --env-file /Users/anaishowland/Documents/agent-hub/.env \
  -e LOG_LEVEL=DEBUG \
  -e BUCKET_NAME=paradigm-shift-job-results \
  -e GOOGLE_CLOUD_PROJECT=evaluation-deployment \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
  -v "$CREDS_FILE:/root/.config/gcloud/application_default_credentials.json:ro" \
  -v "/Users/anaishowland/Documents/agent-hub:/app" -w /app \
  openai-eval:local-amd64 \
  --jobId "openai/local" \
  --task "Check the current stock price for Apple (AAPL) on a financial news website." \
  --taskId "finance-test2" \
  --user "anais" \
  --episode 0 \
  --model "computer-use-preview" \
  --advanced_settings '{"max_steps":25,"temperature":0}'
```

## Run via Cloud Run Jobs
- Use the root FastAPI orchestrator (`agent-hub/main.py`) with `agent_type: "OpenAI"`. The API picks `OPENAI_JOB_NAME` (default `openai-eval`).
```bash
curl -X POST http://localhost:8000/execute-pipeline-tasks \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "62",
    "user_id": "cme2gz7zn000005os2yuj36h8",
    "job_id": "01K2Z5YXJQNMQSJ5HE4R5RVWKM",
    "episode": 0,
    "agent_type": "OpenAI"
  }'
```

## Notes
- Use straight quotes in CLI; flag is `--taskId` (capital D).
- With no URL in the task, the agent starts at Bing and searches.
- On Cloud Run, ADC is provided by the service account (no mounts needed).

## Viewport configuration (single source of truth)
- Default viewport is 1024x768. This size is used for both Playwright's browser context and the OpenAI tool spec, ensuring click coordinates match what the model sees.
- Override via `advanced_settings` when launching the agent:
  - `display_width_px`: integer pixel width
  - `display_height_px`: integer pixel height

Examples:

Docker (local):
```bash
VW=1280
VH=800
xvfb-run -a python -m OpenaiEvaluation.main \
  --jobId "openai/local" \
  --task "..." \
  --taskId "example" \
  --user "anais" \
  --episode 0 \
  --model "computer-use-preview" \
  --advanced_settings "{\"display_width_px\": $VW, \"display_height_px\": $VH, \"max_steps\": 30, \"temperature\": 0}"
```

Docker (via `docker run` with env substitution):
```bash
VW=1366 VH=768 \
docker run --rm \
  -e TASK_ID=mytask -e JOB_ID=openai -e USER_ID=anais -e EPISODE=0 \
  -e TASK_DESCRIPTION="$(printf %s '...' | base64 | tr -d '\n')" \
  -v "/Users/anaishowland/Documents/agent-hub:/app" -w /app \
  openai-eval:local-amd64 \
  /bin/bash -lc "set -e; export TASK_DESCRIPTION_DECODED=\"$(echo \"$TASK_DESCRIPTION\" | base64 --decode)\"; \
  xvfb-run -a python -m OpenaiEvaluation.main \
    --jobId \"$JOB_ID\" \
    --task \"$TASK_DESCRIPTION_DECODED\" \
    --taskId \"$TASK_ID\" \
    --user \"$USER_ID\" \
    --episode \"$EPISODE\" \
    --model \"computer-use-preview\" \
    --advanced_settings '{"display_width_px': '"$VW"', "display_height_px": '"$VH"', "max_steps": 30, "temperature": 0}'"
```

Cloud Run Jobs (body snippet):
```json
{
  "agent_type": "OpenAI",
  "episode": 0,
  "advanced_settings": {
    "display_width_px": 1280,
    "display_height_px": 800,
    "max_steps": 40,
    "temperature": 0
  }
}
```

Notes:
- Keep the same width/height for both the browser viewport and the tool spec (this module does that automatically) to prevent click misalignment.
- If omitted, the agent uses safe defaults 1024x768.

## Files overview (new implementation)
- `main.py`: Thin orchestrator. Launches Playwright, resolves start URL, calls `loop.run_task`, then writes/uploads results.
- `loop.py`: Linear agent loop (model → action → screenshot → follow-up). Builds steps with `model_output.thinking`, `model_output.action`, `interactions`, `state`, and `metadata`.
- `request.py`: Minimal wrapper over OpenAI `responses.create` for initial and follow-up (with `computer_call_output`). Reuses a single client.
- `actions_playwright.py`: Executes one browser action with Playwright; returns `(result_str, state_dict)`.
- `prompt.py`: Single source for system prompt and message helpers; includes `png_bytes_to_data_uri`.
- `keys.py`: Key normalization and combo handling for Playwright.
- `urls.py`: Start URL resolution from env/task text (or Bing fallback).
- `storage.py`: Writes `result.json`; optionally uploads artifacts to GCS.
- `llm.py`: Model mapping (kept to align with other agents’ format).

## High‑level execution flow
1) `main.py` starts Playwright, resolves `start_url`, calls `loop.run_task`.
2) `loop.run_task`:
   - Captures initial screenshot; builds initial messages via `prompt`.
   - `request.create_initial` → parse response → get `thinking`, `action`, `call_id`.
   - `actions_playwright.perform` executes one action; capture screenshot.
   - Send `computer_call_output` (PNG data URI) via `request.create_followup` (threaded with `previous_response_id`).
   - Append one `step` with `model_output`, `interactions`, `result`, `state`, `metadata`; repeat until final.
3) `main.py` persists `result.json` (and optionally uploads to GCS) via `storage.py`.

## Rebuild and run this agent
- Rebuild only the OpenAI agent image (neurosim‑base already built):
```bash
cd /Users/anaishowland/Documents/agent-hub
docker build -t openai-eval:local-amd64 -f OpenaiEvaluation/Dockerfile .
```
- Run locally (headful): see the “Run locally (headful)” section above.