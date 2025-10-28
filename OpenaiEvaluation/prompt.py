from __future__ import annotations

"""Prompt helpers for the CUA loop.

This module replaces the older `conversation.py` and should be the single
source of truth for system text and message construction.
"""

import base64
from typing import Any, Dict, List, Tuple


SHORT_SYSTEM_PROMPT = (
    "You are a browser automation agent. Complete the user's task step by step "
    "by interacting with web pages. Output one browser action per step (click, "
    "type, keypress, scroll, goto, back, forward, reload, wait). Click an input "
    "before typing. If blocked (logins/captchas), briefly explain and stop. When "
    "done, output a short final summary."
)


def system_text(override: str | None = None) -> str:
    return (override or "").strip() or SHORT_SYSTEM_PROMPT


def build_initial_messages(
    system_prompt: str,
    task_text: str,
    screenshot_png: bytes,
    system_inserts: List[str] | None = None,
) -> List[Dict[str, Any]]:
    # Ensure non-empty image payload; if empty, use 1x1 transparent pixel
    if not screenshot_png:
        screenshot_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wwAAgMBgQd8r3QAAAAASUVORK5CYII="
        )
    b64 = base64.b64encode(screenshot_png).decode()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]}
    ]
    if system_inserts:
        for txt in system_inserts:
            messages.append({"role": "system", "content": [{"type": "input_text", "text": txt}]})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": f"Task: {task_text}"},
                {"type": "input_image", "image_url": f"data:image/png;base64,{b64}", "detail": "low"},
            ],
        }
    )
    return messages


def build_followup_messages(
    screenshot_png: bytes,
    system_inserts: List[str] | None = None,
) -> List[Dict[str, Any]]:
    if not screenshot_png:
        screenshot_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wwAAgMBgQd8r3QAAAAASUVORK5CYII="
        )
    b64 = base64.b64encode(screenshot_png).decode()
    messages: List[Dict[str, Any]] = []
    if system_inserts:
        for txt in system_inserts:
            messages.append({"role": "system", "content": [{"type": "input_text", "text": txt}]})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": f"data:image/png;base64,{b64}", "detail": "low"},
            ],
        }
    )
    return messages


def png_bytes_to_data_uri(png: bytes) -> str:
    b64 = base64.b64encode(png).decode()
    return f"data:image/png;base64,{b64}"


