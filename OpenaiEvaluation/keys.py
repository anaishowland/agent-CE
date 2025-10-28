from __future__ import annotations

"""Key normalization and pressing helpers for async Playwright.

Provides:
- `normalize_key_name`: maps friendly names and synonyms to Playwright names.
- `press_keys`: sends either a list of keys (with optional `+` combos) or a
  single key string to the page.
"""

from typing import List


KEY_NAME_MAP = {
    "ENTER": "Enter",
    "RETURN": "Enter",
    "TAB": "Tab",
    "ESC": "Escape",
    "ESCAPE": "Escape",
    "BACKSPACE": "Backspace",
    "DELETE": "Delete",
    "INSERT": "Insert",
    "SPACE": "Space",
    "SLASH": "Slash",         # "/" convenience alias
    "NUMPADDIVIDE": "NumpadDivide",
    "BACKSLASH": "Backslash", # "\\" convenience alias
    "CAPSLOCK": "CapsLock",
    "ARROWDOWN": "ArrowDown",
    "ARROWUP": "ArrowUp",
    "ARROWLEFT": "ArrowLeft",
    "ARROWRIGHT": "ArrowRight",
    "PAGEUP": "PageUp",
    "PAGEDOWN": "PageDown",
    "HOME": "Home",
    "END": "End",
    "SHIFT": "Shift",
    "CONTROL": "Control",
    "CTRL": "Control",
    "ALT": "Alt",
    "OPTION": "Alt",
    "CMD": "Meta",
    "COMMAND": "Meta",
    "META": "Meta",
    "WIN": "Meta",
    "WINDOWS": "Meta",
    "SUPER": "Meta",
}


def normalize_key_name(key: str) -> str:
    """Normalize a key name to what Playwright expects.

    Accepts synonyms (Enter/Return, Esc/Escape, Ctrl/Control, Cmd/Meta, etc.)
    and function keys.
    """
    k = (key or "").strip()
    if not k:
        return ""
    # Handle punctuation tokens exactly as typed
    if k == "/":
        return "Slash"
    if k == "\\":
        return "Backslash"

    upper = k.upper()
    if upper in KEY_NAME_MAP:
        return KEY_NAME_MAP[upper]
    # Function keys
    if (upper.startswith("F") and upper[1:].isdigit() and 1 <= int(upper[1:]) <= 24):
        return f"F{int(upper[1:])}"
    return k


async def press_keys(page, raw_keys: List[str] | None, single: str | None) -> None:
    """Press list of keys or a single key on the page.

    Supports combo notation with `+` (e.g., "Ctrl+L"). For combos, all but the
    last token are pressed down as modifiers, then the last is pressed, then
    modifiers are released.
    """
    tokens: List[str] = []
    if raw_keys:
        for item in raw_keys:
            if not isinstance(item, str):
                continue
            parts = [p for p in item.replace(" ", "").split("+") if p]
            if parts:
                tokens.append("+")
                tokens.extend(parts)
    elif isinstance(single, str) and single.strip():
        parts = [p for p in single.replace(" ", "").split("+") if p]
        tokens.extend(parts)

    if not tokens:
        return

    combo: List[str] = []

    async def commit(keys: List[str]) -> None:
        if not keys:
            return
        mapped = []
        for k in keys:
            m = normalize_key_name(k)
            if m:
                mapped.append(m)
        if not mapped:
            return
        if len(mapped) == 1:
            await page.keyboard.press(mapped[0])
            return
        modifiers, last = mapped[:-1], mapped[-1]
        for m in modifiers:
            await page.keyboard.down(m)
        await page.keyboard.press(last)
        for m in reversed(modifiers):
            await page.keyboard.up(m)

    for t in tokens:
        if t == "+":
            await commit(combo)
            combo = []
        else:
            combo.append(t)
    await commit(combo)


