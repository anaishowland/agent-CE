from __future__ import annotations

"""Core CUA loop: model -> action -> screenshot -> model.

This mirrors the simplicity of `cua_docker_loop.py` while using Playwright for
action execution. It returns a result dictionary compatible with our schema.
"""

 
import time
import base64
import logging
from contextlib import suppress
from typing import Any, Dict, List, Tuple

from . import request as req
from . import actions_playwright
from .prompt import build_initial_messages, png_bytes_to_data_uri


# Cooperative shutdown flag toggled by signal handler in main
STOP_REQUESTED: bool = False


def request_stop() -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


async def capture_screenshot(page, last_png: bytes | None = None) -> bytes | None:
    # Deterministic, short attempts to avoid long blocking
    try:
        return await page.screenshot(full_page=False, timeout=30000)
    except Exception as e:
        with suppress(Exception):
            logging.warning("[SHOT] screenshot attempt 1 failed (timeout=30000ms): %s", e)
    # Element-based fallback
    try:
        body = await page.query_selector("body")
        if body is not None:
            return await body.screenshot(timeout=5000)
    except Exception as e:
        with suppress(Exception):
            logging.warning("[SHOT] element screenshot fallback failed: %s", e)
    # Last resort: return previous successful PNG (may be None at very first step)
    return last_png


def _placeholder_png() -> bytes:
    # 1x1 transparent PNG (base64)
    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wwAAgMBgQd8r3QAAAAASUVORK5CYII="
    )
    try:
        return base64.b64decode(b64)
    except Exception:
        # Extremely unlikely; return empty bytes as ultimate fallback
        return b""


def _parse_response(resp: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any] | None, str | None, Dict[str, int], List[str]]:
    final_text = ""
    collected_reasoning: List[str] = []
    action: Dict[str, Any] | None = None
    action_call_id: str | None = None
    usage_dict: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    pending_safety_ids: List[str] = []

    def _collect_reasoning_blocks(obj: Dict[str, Any]) -> None:
        # Collect detailed reasoning text
        for rc in obj.get("content", []) or []:
            if rc.get("type") == "reasoning_text":
                txt = rc.get("text", "")
                if txt:
                    collected_reasoning.append(txt)
        # Collect summary reasoning text
        summary = obj.get("summary")
        if isinstance(summary, list):
            for s in summary:
                txt = (s or {}).get("text", "")
                if txt:
                    collected_reasoning.append(txt)

    for item in resp.get("output", []) or []:
        itype = item.get("type")
        if itype == "output_text":
            final_text = item.get("text", "")
        elif itype == "message":
            for c in item.get("content", []) or []:
                ctype = c.get("type")
                if ctype == "output_text":
                    if not final_text:
                        final_text = c.get("text", "")
                elif ctype == "reasoning":
                    _collect_reasoning_blocks(c)
        elif itype == "reasoning":
            _collect_reasoning_blocks(item)
        elif itype == "computer_call":
            action = item.get("action") or item
            action_call_id = item.get("call_id") or item.get("id") or action_call_id
        # Safety/pending checks may appear under various keys; collect any ids we find
        # Common patterns observed: item["pending_safety_checks"], item["safety_checks"], or nested under action
        try:
            for key in ("pending_safety_checks", "safety_checks", "checks"):
                checks = item.get(key)
                if isinstance(checks, list):
                    for chk in checks:
                        cid = (chk or {}).get("id") if isinstance(chk, dict) else None
                        if isinstance(cid, str) and cid:
                            pending_safety_ids.append(cid)
        except Exception:
            pass

    try:
        usage = resp.get("usage") or {}
        pt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        ct = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        tt = int(usage.get("total_tokens") or (pt + ct))
        usage_dict = {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": tt}
    except Exception:
        pass

    reasoning_text = "\n".join([t for t in collected_reasoning if t]).strip()
    # Fallback scan at top-level in case checks aren't attached to items
    try:
        for key in ("pending_safety_checks", "safety_checks", "checks"):
            checks = resp.get(key)
            if isinstance(checks, list):
                for chk in checks:
                    cid = (chk or {}).get("id") if isinstance(chk, dict) else None
                    if isinstance(cid, str) and cid:
                        pending_safety_ids.append(cid)
    except Exception:
        pass

    # Deduplicate safety ids while preserving order
    seen = set()
    dedup_ids = [i for i in pending_safety_ids if not (i in seen or seen.add(i))]
    return final_text, reasoning_text, action, action_call_id, usage_dict, dedup_ids


async def run_task(
    page,
    task_text: str,
    model: str,
    max_steps: int,
    temperature: float,
    start_url: str,
    screenshot_dir: str,
    system_prompt: str,
    display_width: int = 1024,
    display_height: int = 768,
) -> Dict[str, Any]:
    # Reset cooperative stop flag at the start of each run
    global STOP_REQUESTED
    STOP_REQUESTED = False

    # Robust navigation: softer wait, then best-effort network idle and visibility checks
    nav_started = time.time()
    with suppress(Exception):
        logging.info("[NAV] goto %s wait_until=domcontentloaded", start_url)
    try:
        await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        # Retry once via reload with the same softer wait
        with suppress(Exception):
            logging.warning("[NAV] goto failed (%s); attempting reload domcontentloaded", e)
        with suppress(Exception):
            await page.reload(wait_until="domcontentloaded", timeout=60000)
    # Best-effort network quiet
    with suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=30000)
    # Ensure body visible and settle briefly
    with suppress(Exception):
        await page.wait_for_selector("body", state="visible", timeout=15000)
    # Best-effort: ensure full readiness before first screenshot
    with suppress(Exception):
        await page.wait_for_function('document.readyState==="complete"', timeout=15000)
    with suppress(Exception):
        await page.wait_for_timeout(500)
    with suppress(Exception):
        logging.info("[NAV] completed in %dms", int((time.time() - nav_started) * 1000))
    first_png = await capture_screenshot(page, None)
    if first_png is None:
        # Guarantee an image exists for downstream saves and model input
        first_png = _placeholder_png()
    # Save initial screenshot as step 0
    import os
    os.makedirs(screenshot_dir, exist_ok=True)
    first_path = os.path.join(screenshot_dir, f"screenshot_0.png")
    try:
        if first_png is not None:
            with open(first_path, "wb") as f:
                f.write(first_png)
    except Exception:
        pass
    messages = build_initial_messages(system_prompt, task_text, first_png)

    steps: List[Dict[str, Any]] = []
    tokens: List[Dict[str, int]] = []
    prev_id: str | None = None
    repeated: int = 0
    last_sig: Tuple[Any, ...] | None = None
    

    resp = req.create_initial(
        model,
        messages,
        temperature,
        display_width=display_width,
        display_height=display_height,
    )

    last_png: bytes | None = first_png

    for step_index in range(max_steps):
        if STOP_REQUESTED:
            return {
                "success": False,
                "results": "Terminated",
                "steps": steps,
                "tokens": tokens,
            }
        final_text, reasoning, action, call_id, usage_counts, safety_ids = _parse_response(resp)

        if usage_counts["total_tokens"] > 0:
            tokens.append(usage_counts)

        if not action:
            # If the model stopped without an action, determine success based on final_text
            ft = (final_text or reasoning or "").lower()
            blocker_triggers = [
                "captcha",
                "security verification",
                "cloudflare",
                "verifying you are human",
                "verify you are human",
                "human verification",
                "i am not a robot",
                "access denied",
                "network security block",
                "connectivity problem",
                "network error",
                "verification puzzle",
                "would you like to try",
                "would you like me to try",
                "robot check",
                "error message",
                "not accessible",
                "verification step",
                "verification"
            ]
            blocked = any(t in ft for t in blocker_triggers)
            return {
                "success": not blocked and bool(final_text or reasoning),
                "results": (final_text or reasoning) if not blocked else (final_text or reasoning or "Blocked"),
                "steps": steps,
                "tokens": tokens,
            }

        started_at = time.time()
        result_str, state = await actions_playwright.perform(page, action)
        # Determine action type early for wait coalescing behavior
        atype = str((action or {}).get("type", "")).lower()
        # Always capture a fresh screenshot so the model sees latest UI
        screenshot_png = await capture_screenshot(page, last_png)
        # Persist every step (including waits) so screenshots are always saved
        persist_step = True
        # Save post-action screenshot for this step (1-based after initial) only if persisting
        import os
        shot_path = os.path.join(screenshot_dir, f"screenshot_{step_index + 1}.png") if persist_step else ""
        if persist_step:
            try:
                # If new capture failed, persist last known good image or the initial placeholder
                effective_png_save = screenshot_png or last_png or first_png
                if effective_png_save is not None:
                    with open(shot_path, "wb") as f:
                        f.write(effective_png_save)
                    # Update last_png only when a new capture exists; keep previous if fallback
                    if screenshot_png is not None:
                        last_png = screenshot_png
                else:
                    shot_path = ""
            except Exception:
                shot_path = ""
        else:
            # Should not occur since persist_step is True; keep last_png fresh just in case
            if screenshot_png is not None:
                last_png = screenshot_png

        # Interactions list based on the executed action (skip emitting for wait-only step)
        interactions: List[Dict[str, Any]] = []
        if atype in ("click", "left_click", "mouse_click"):
            interactions.append({"click": {"x": action.get("x"), "y": action.get("y"), "button": action.get("button", "left")}})
        elif atype in ("double_click", "doubleclick"):
            interactions.append({"double_click": {"x": action.get("x"), "y": action.get("y")}})
        elif atype == "type":
            txt = action.get("text", "") or ""
            interactions.append({"typed_chars": len(txt)})
        elif atype in ("keypress", "key"):
            keys = action.get("keys") if isinstance(action.get("keys"), list) else None
            key_single = action.get("key") or action.get("text")
            keys_norm = keys if keys is not None else ([key_single] if key_single else [])
            interactions.append({"keys": keys_norm})
        elif atype == "scroll":
            interactions.append({"scroll": {"x": int(action.get("scroll_x", action.get("x", 0)) or 0), "y": int(action.get("scroll_y", action.get("y", 0)) or 0)}})
        elif atype in ("goto", "open_url"):
            interactions.append({"goto": {"url": action.get("url", "")}})
        elif atype == "wait":
            # Coalesced; do not emit a separate step
            pass
        elif atype in ("drag", "left_click_drag"):
            # Normalize to start/end if present or path first/last
            entry: Dict[str, Any] = {}
            path = action.get("path")
            if isinstance(path, list) and len(path) >= 2:
                entry = {"from": path[0], "to": path[-1]}
            else:
                cs = action.get("coordinate_start") or action.get("start")
                ce = action.get("coordinate_end") or action.get("end")
                if cs and ce:
                    entry = {"from": cs, "to": ce}
            interactions.append({"drag": entry or {}})

        if persist_step:
            step_dict = {
                "step": len(steps),
                "model_output": {"thinking": reasoning, "action": action},
                "interactions": interactions,
                "result": result_str,
                "state": {
                    "url": state.get("url", ""),
                    "title": state.get("title", ""),
                    "interacted_element": state.get("interacted_element"),
                    "screenshot_path": shot_path,
                },
                "metadata": {"started_at": started_at, "duration_ms": int((time.time() - started_at) * 1000)},
            }
            steps.append(step_dict)

        if persist_step:
            sig = (
                str(action.get("type", "")).lower(),
                action.get("x"),
                action.get("y"),
                action.get("text"),
                action.get("url"),
            )
            if sig == last_sig:
                repeated += 1
            else:
                repeated = 0
            last_sig = sig

        # Loop breaker and bot-wall detection (disabled by default; enable with ENABLE_LOOP_GUARDS=true)
        _guards_env = str((__import__("os").getenv("ENABLE_LOOP_GUARDS", "false") or "")).strip().lower()
        _guards_enabled = _guards_env in ("1", "true", "yes")
        if _guards_enabled:
            try:
                REPEAT_LIMIT = int(__import__("os").getenv("REPEAT_LIMIT", "6") or 6)
            except Exception:
                REPEAT_LIMIT = 6
            if repeated >= REPEAT_LIMIT:
                return {
                    "success": False,
                    "results": f"Aborting: loop detected after {repeated+1} identical actions.",
                    "steps": steps,
                    "tokens": tokens,
                }
            thinking_lower = (final_text or reasoning or "").lower()
            try:
                url_now = (state.get("url") or "").lower()
                title_now = (state.get("title") or "").lower()
            except Exception:
                url_now = title_now = ""
            wall_hits = (
                "captcha",
                "verify you are human",
                "are you human",
                "cloudflare",
                "puzzle",
                "unusual traffic",
                "access denied",
            )
            if any(w in thinking_lower for w in wall_hits) or any(w in title_now for w in wall_hits):
                return {
                    "success": False,
                    "results": "Blocked by verification or bot gate. Stopping early.",
                    "steps": steps,
                    "tokens": tokens,
                }

        # Simple repeat counter only (no screenshot hashing)

        # Follow-up: send computer_call_output per Responses API accepted values
        # Ensure we never send an empty image; fall back to placeholder
        effective_png = screenshot_png or last_png or first_png or _placeholder_png()
        data_uri = png_bytes_to_data_uri(effective_png)
        computer_output: Dict[str, Any] = {
            "type": "computer_call_output",
            "call_id": call_id,
            "output": {
                "type": "input_image",
                "image_url": data_uri,
                "detail": "low",
            },
        }
        if safety_ids:
            with suppress(Exception):
                computer_output["acknowledged_safety_checks"] = [{"id": sid} for sid in safety_ids if sid]
        prev_id = resp.get("id") or prev_id
        try:
            resp = req.create_followup(
                model,
                previous_response_id=str(prev_id or ""),
                input_items=[computer_output],
                temperature=temperature,
                display_width=display_width,
                display_height=display_height,
            )
        except Exception as e:
            with suppress(Exception):
                logging.error("[HTTP] followup failed: %s", e)
            return {
                "success": False,
                "results": "Run interrupted due to follow-up error.",
                "steps": steps,
                "tokens": tokens,
            }

    return {
        "success": False,
        "results": "Maximum steps reached without a final answer.",
        "steps": steps,
        "tokens": tokens,
    }


