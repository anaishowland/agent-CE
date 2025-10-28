# Refactor Status — OpenAI CUA

Source plan: `OpenaiEvaluation/OpenAI_CUA_Refactor_Plan.md`

## Module setup (5.1)
- [x] `request.py` (OpenAI client wrapper)
- [x] `actions_playwright.py` (action dispatcher)
- [x] `loop.py` (model → action → screenshot → model)
- [x] `prompt.py` (short system text + message helpers) — replaces `conversation.py`
- [x] `storage.py` (local write + optional GCS)
- [ ] `agent.py` (not needed; kept `main.py` class)

## Keep standardized class surface (5.2)
- [x] Preserve `OpenaiEvaluation` class with `__init__`, `get_llm`, `run`
- [x] `run()` launches Playwright, resolves start URL, calls `loop.run_task`, persists results

## Loop parity (5.3)
- [x] Stateless loop created in `loop.py`
- [x] Uses `prompt.build_initial_messages/build_followup_messages`
- [x] Threads via `previous_response_id`
- [x] Adds `computer_call_output` follow-ups with screenshot data URI
- [ ] Safety checks ack: structure in place (empty list); implement if model returns checks
- [ ] Minimal anti‑stuck nudges: basic repeat tracking only

## Actions (5.4)
- [x] Narrow dispatcher in `actions_playwright.py`
- [x] Returns `(result_str, state_dict)`
- [x] Consolidated: removed `operator_async.py`; direct Playwright ops live in `actions_playwright.py`

## Requests (5.5)
- [x] Unified on OpenAI client in `request.py`
- [x] Single tool `computer_use_preview` with environment `browser`

## Prompt & conversation (5.6)
- [x] Short system text and message building centralized in `prompt.py`
- [x] Removed `conversation.py`

## Results & storage (5.7)
- [x] Each step built once per iteration in the loop
- [x] Local `result.json`; optional GCS upload via `storage.py`

## Keep-only-browser tool (5.8)
- [x] Exactly one tool registered

## Start URL (5.9)
- [x] Kept `urls.resolve_start_url()` logic

## Practical fixes (7)
- [~] Replace `_responses_create()` with `request.py`: delegated loop uses client; legacy helper still present in `main.py` (cleanup next)
- [~] Delete duplicate key helpers in `main.py`: legacy helpers remain but unused (cleanup next)
- [x] Move action dispatch to `actions_playwright.py`
- [x] Single screenshot helper inside loop
- [x] Use `prompt.build_initial_messages/build_followup_messages` consistently in loop
- [x] Keep existing `urls.py`, `entry.sh`, Docker, and GCS schema
- [x] Single navigation responsibility: handled inside `loop.run_task` (removed duplicate in `main.py`)
- [x] Interactions list per step added
- [x] Centralized `png_bytes_to_data_uri` in `prompt.py`
- [x] Reuse a single OpenAI client instance in `request.py`
- [x] Tightened `parse_response` to return `(final_text, thinking, action, call_id, usage)`
- [x] Pruned screenshot hashing; kept a simple repeat counter only
- [x] Added error-body logging for 4xx from `/v1/responses` to speed debugging
- [x] Ensure local `result.json` is written and path logged; add optional `debug-runs/*.result.json` copy

## Known issues / next steps
- Remove any lingering unused imports from `main.py`.
- Add optional safety-check acknowledgements if model returns them.
- Implement light anti‑stuck sequence (Enter → small scroll → reload) when repeated actions detected.
- Viewport configurability documented in README and wired via `advanced_settings.display_width_px`/`display_height_px` (defaults 1024x768). Tool spec size is kept in sync with Playwright viewport.

## Divergences vs `third_party/cua-sdk/cua_docker` (after refactor)
- Environment/tool: We use `environment: "browser"` vs sdk’s `"linux"` — intentional for Playwright browser runs.
- Screenshot transport: We pass base64 data URLs like sdk; file saving is an added local artifact behavior (not in sdk loop).
- Action backend: sdk uses `xdotool` and `import`; we use Playwright directly in `actions_playwright.py`.
- Storage: sdk loop is stateless about artifact persistence; we persist `result.json` and screenshots and optionally upload to GCS.
- Safety checks: we prepare `acknowledged_safety_checks` in the output; still need to read and include pending checks from model when present — TODO.
- Nudge/unstick: sdk has minimal ack; we track repeats and can add small nudges — TODO to refine.

