from __future__ import annotations

"""Playwright action dispatcher used by the CUA loop.

This module provides a tiny router that maps a normalized action dict to
Playwright operations via the existing `OperatorAsync` adapter.
Each helper returns a `(result_str, state_dict)` tuple.
"""

from typing import Any, Dict, Tuple

from playwright.async_api import Page
from .keys import press_keys


async def perform(page: Page, action: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    action_type = str(action.get("type", "")).lower()
    state: Dict[str, Any] = {}
    result: str = ""

    async def _collect_state() -> None:
        try:
            state["url"] = await page.evaluate("() => location.href")
        except Exception:
            try:
                state["url"] = page.url
            except Exception:
                state["url"] = ""
        try:
            state["title"] = await page.title()
        except Exception:
            state["title"] = ""

    if action_type in ("click", "left_click", "mouse_click"):
        x = int(action.get("x", 0) or 0)
        y = int(action.get("y", 0) or 0)
        button = action.get("button", "left") or "left"
        try:
            handle = await page.evaluate_handle(
                "(p) => document.elementFromPoint(p.x, p.y)", {"x": int(x), "y": int(y)}
            )
            elem = handle.as_element() if handle else None
            if elem is not None:
                try:
                    await elem.click()
                except Exception:
                    await page.mouse.click(x, y, button=button)
            else:
                await page.mouse.click(x, y, button=button)
        except Exception:
            await page.mouse.click(x, y, button=button)
        result = f"Clicked at ({x},{y}) with button={button}"
        before_url = page.url
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
                    await page.wait_for_timeout(800)
        except Exception:
            pass
        state["interacted_element"] = {"x": x, "y": y, "button": button}
    elif action_type in ("double_click", "doubleclick"):
        x = int(action.get("x", 0) or 0)
        y = int(action.get("y", 0) or 0)
        await page.mouse.dblclick(x, y)
        result = f"Double-clicked at ({x},{y})"
        await _collect_state()
        state["interacted_element"] = {"x": x, "y": y}
    elif action_type == "type":
        text = action.get("text", "") or ""
        await page.keyboard.type(text)
        result = f"Typed {len(text)} chars"
        await _collect_state()
    elif action_type in ("keypress", "key"):
        keys = action.get("keys") if isinstance(action.get("keys"), list) else None
        key_single = action.get("key") or action.get("text")
        await press_keys(page, keys, key_single)
        result = "Pressed keys"
        await _collect_state()
    elif action_type == "scroll":
        sx = int(action.get("scroll_x", action.get("x", 0)) or 0)
        sy = int(action.get("scroll_y", action.get("y", 0)) or 0)
        await page.evaluate(f"window.scrollBy({int(sx)}, {int(sy)})")
        result = f"Scrolled by ({sx},{sy})"
        await _collect_state()
    elif action_type in ("move", "hover"):
        x = int(action.get("x", 0) or 0)
        y = int(action.get("y", 0) or 0)
        await page.mouse.move(x, y)
        result = f"Moved to ({x},{y})"
        await _collect_state()
        state["interacted_element"] = {"x": x, "y": y}
    elif action_type in ("drag", "left_click_drag"):
        # Support drag by either a two-point path or coordinate_start/coordinate_end
        sx = sy = ex = ey = None
        path = action.get("path")
        if isinstance(path, list) and len(path) >= 2:
            try:
                start = path[0] or {}
                end = path[-1] or {}
                sx = int((start.get("x") if isinstance(start, dict) else start[0]))
                sy = int((start.get("y") if isinstance(start, dict) else start[1]))
                ex = int((end.get("x") if isinstance(end, dict) else end[0]))
                ey = int((end.get("y") if isinstance(end, dict) else end[1]))
            except Exception:
                sx = sy = ex = ey = None
        if sx is None or sy is None or ex is None or ey is None:
            cs = action.get("coordinate_start") or action.get("start")
            ce = action.get("coordinate_end") or action.get("end")
            try:
                if isinstance(cs, dict):
                    sx, sy = int(cs.get("x", 0)), int(cs.get("y", 0))
                elif isinstance(cs, (list, tuple)) and len(cs) == 2:
                    sx, sy = int(cs[0]), int(cs[1])
                if isinstance(ce, dict):
                    ex, ey = int(ce.get("x", 0)), int(ce.get("y", 0))
                elif isinstance(ce, (list, tuple)) and len(ce) == 2:
                    ex, ey = int(ce[0]), int(ce[1])
            except Exception:
                sx = sy = ex = ey = None
        if sx is None or sy is None or ex is None or ey is None:
            result = "Invalid drag path"
            await _collect_state()
        else:
            button = (action.get("button") or "left").lower()
            steps = int(action.get("steps", 12) or 12)
            await page.mouse.move(sx, sy)
            await page.mouse.down(button=button)
            await page.mouse.move(ex, ey, steps=max(1, steps))
            await page.mouse.up(button=button)
            result = f"Dragged from ({sx},{sy}) to ({ex},{ey})"
            before_url = page.url
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=8000)
            except Exception:
                pass
            await _collect_state()
            try:
                if state.get("url") and state["url"] != before_url:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        await page.wait_for_timeout(800)
            except Exception:
                pass
            state["interacted_element"] = {
                "from": {"x": sx, "y": sy},
                "to": {"x": ex, "y": ey},
                "button": button,
            }
    elif action_type in ("goto", "open_url"):
        url = action.get("url", "") or ""
        if url:
            await page.goto(url)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=12000)
            except Exception:
                try:
                    await page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
            result = f"Navigated to {url}"
        else:
            result = "Goto requested without URL"
        await _collect_state()
    elif action_type == "back":
        await page.go_back()
        result = "Navigated back"
        await _collect_state()
    elif action_type == "forward":
        await page.go_forward()
        result = "Navigated forward"
        await _collect_state()
    elif action_type == "wait":
        import asyncio as _a
        delay = float(action.get("duration", 1) or 1)
        await _a.sleep(max(0.0, min(10.0, delay)))
        result = f"Waited {delay:.2f}s"
        await _collect_state()
    elif action_type == "screenshot":
        png = await page.screenshot(full_page=False)
        result = f"Captured screenshot ({len(png)} bytes)"
        await _collect_state()
    else:
        result = f"Unknown action: {action_type}"
        await _collect_state()

    return result, state


