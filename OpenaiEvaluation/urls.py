from __future__ import annotations

"""Start URL resolution for tasks.

Order of precedence:
1. `START_URL` environment variable (explicit override)
2. First explicit http(s) URL found in the task text
3. First bare domain found in the task text, normalized to https://domain/
4. Default: https://www.bing.com/
"""

import os
import re


def resolve_start_url(task_text: str) -> str:
    """Resolve a sensible starting URL for the browser given a task string."""
    start_url = (os.getenv("START_URL", "") or "").strip()
    if start_url:
        return start_url
    if isinstance(task_text, str):
        m = re.search(r"https?://[^\s)]+", task_text)
        if m:
            return m.group(0)
        dm = re.search(r"\b([a-zA-Z0-9.-]+\.(com|org|net|io|ai|edu|gov|co|uk|de|jp|ca|us|au|ch|nl|se|no|es|fr))\b", task_text)
        if dm:
            return f"https://{dm.group(1)}/"
    return "https://www.bing.com/"


