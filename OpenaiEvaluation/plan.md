# **What’s going wrong**

## **1\) Coordinate system mismatch (big one)**

* In main.py you create the Playwright context with **viewport 1280×1080**:

```
browser.new_context(viewport={"width": 1280, "height": 1080}, ...)
```

* 

* In request.py you advertise the computer-use tool as **display\_width=1024, display\_height=768** by default:

```
def tool_spec(display_width: int = 1024, display_height: int = 768) -> List[Dict[str, Any]]:
    return [{
        "type": "computer_use_preview",
        "display_width": int(display_width),
        "display_height": int(display_height),
        "environment": "browser",
    }]
```

* 

* Your loop calls req.create\_initial(model, messages, temperature) and req.create\_followup(...) **without** overriding these defaults, so the model believes the screen is 1024×768 while you actually render 1280×1080. That will consistently skew clicks and drags, which looks exactly like “it navigates right but can’t click the right thing.”

Docs and Azure’s examples show that the tools entry’s display\_width/display\_height define the model’s coordinate system, which must match your real viewport. 

## **2\) No hard “loop breaker” and weak bot-wall detection**

* In loop.py you compute a simple signature of the last action (type, x, y, text, url) and increment repeated, but you **never act on it**. When the model gets stuck (captcha, slider, cookie wall), it will happily repeat the same click/drag forever until max\_steps hits.

* Your “blocked” check only runs when the model returns **no action**. On real sites, bot screens often still elicit actions (drag slider, click “verify”, refresh), so you never trip that guard.

* Your attached run (result\_oai2.json) shows the model stuck on **Viator’s human verification puzzle**:

  * 50 steps total: 23 clicks, 22 waits, 5 drags.

  * URL stays on https://www.viator.com/ the whole time.

  * First thought is literally “Solving puzzle to proceed on Viator”.

  * Ends with “Maximum steps reached…”.

     That’s a classic bot-wall loop.

## **3\) Flaky timing after clicks**

* In actions\_playwright.py, after a coordinate click you do not reliably wait for page settle. You capture a screenshot immediately, but if the page is still transitioning, the model reasons on stale frames and repeats the same action.

## **4\) Step budget is being consumed by waits**

* The agent often inserts many wait steps. You must still return a screenshot after each, so they eat into your step cap quickly. There’s not a perfect fix, but better settle-wait logic after interactions reduces the model’s need to “wait again”.

---

# **Concrete fixes**

Below are minimal changes that keep your structure but address the core issues.

## **A) Make the tool’s display size match your Playwright viewport**

**main.py** — keep a single source of truth for viewport, pass it down:

```
# When creating the context
viewport = {"width": 1280, "height": 1080}
context = await browser.new_context(
    viewport=viewport,
    ignore_https_errors=True,
    bypass_csp=True,
)

# Pass viewport into the loop so requests can advertise matching tool dims
result = await loop.run_task(
    page=page,
    task_text=task["name"],
    model=model_name,
    max_steps=int(os.getenv("MAX_STEPS", "50")),
    temperature=float(os.getenv("TEMPERATURE", "0.1")),
    start_url=resolve_start_url(task["name"]),
    screenshot_dir=screenshot_dir,
    system_prompt=os.getenv("SYSTEM_PROMPT", ""),
    display_width=viewport["width"],
    display_height=viewport["height"],
)
```

**loop.py** — accept and forward the display dims to request.py:

```
async def run_task(page, task_text, model, max_steps, temperature, start_url,
                   screenshot_dir, system_prompt, display_width=1280, display_height=1080):
    ...
    messages = prompt.build_initial_messages(system_prompt, task_text, first_png)
    resp = req.create_initial(model, messages, temperature,
                              display_width=display_width, display_height=display_height)
    ...
    computer_output = {
        "type": "computer_call_output",
        "call_id": call_id,
        "output": {
            "type": "input_image",
            "image_url": data_uri,
            "detail": "low",
        },
        "acknowledged_safety_checks": [{"id": sid} for sid in safety_ids] if safety_ids else None,
    }
    resp = req.create_followup(model,
                               previous_response_id=str(prev_id or ""),
                               input_items=[computer_output],
                               temperature=temperature,
                               display_width=display_width,
                               display_height=display_height)
```

This alone should dramatically improve click accuracy. The official examples explicitly show the tool taking the declared display\_width/height to establish the model’s action coordinate frame. 

## **B) Add a robust loop breaker and better bot-wall detection**

**loop.py** — right after you compute sig and repeated:

```
REPEAT_LIMIT = int(os.getenv("REPEAT_LIMIT", "6"))

# Abort if the model repeats the exact same action too many times
if repeated >= REPEAT_LIMIT:
    return {
        "success": False,
        "results": f"Aborting: loop detected on {state.get('url','')} after {repeated+1} identical actions.",
        "steps": steps,
        "tokens": tokens,
    }

# Lightweight bot-wall heuristics based on the page title/url and model "thinking"
thinking = (final_text or reasoning or "").lower()
url_now = (state.get("url") or "").lower()
title_now = (state.get("title") or "").lower()
wall_hits = ("captcha", "verify you are human", "are you human", "cloudflare", "puzzle", "unusual traffic", "access denied")
if any(w in thinking for w in wall_hits) or any(w in title_now for w in wall_hits):
    return {
        "success": False,
        "results": "Blocked by bot or verification gate. Stopping instead of looping.",
        "steps": steps,
        "tokens": tokens,
    }
```

This makes captchas and sliders fail fast instead of chewing your step budget.

## **C) Wait correctly after interactions**

**actions\_playwright.py** — after any click or drag, add a short stabilization, and if URL changed, wait for load/network idle:

```
# Example for click branch
before_url = page.url
await page.mouse.click(x, y, button=button)

# small settle to let transitions begin
try:
    await page.wait_for_load_state("domcontentloaded", timeout=8000)
except Exception:
    pass

await _collect_state()

# If navigation happened, wait a bit more for resources
try:
    if state.get("url") and state["url"] != before_url:
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            # fallback small sleep to avoid tight loops
            await page.wait_for_timeout(800)
except Exception:
    pass
```

Do the same pattern for double\_click, drag, and goto (extend goto wait to 12–15s for heavier sites).

