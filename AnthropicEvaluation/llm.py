import os
from typing import Optional


def get_llm_model(model: Optional[str]) -> str:
    """
    Normalize incoming CLAUDE model env to a canonical latest by default.
    Enforce the latest unless ALLOW_NON_LATEST=true is set in the env.
    Computer-use tool version and beta version are configured via envs:
    - ANTHROPIC_TOOL_VERSION (default: computer_20250124)
    - ANTHROPIC_BETA_VERSION (default: computer-use-2025-01-24)
    """
    latest_model = "claude-sonnet-4-20250514"
    allow_non_latest = (str(model or "").strip() and (os.getenv("ALLOW_NON_LATEST", "false").strip().lower() in {"1","true","yes"}))
    chosen = (model or latest_model).strip() or latest_model
    if not allow_non_latest:
        # If caller didn't pass exactly the latest, force it
        chosen = latest_model
    # Use @date naming only when routing via Vertex; direct API expects dash naming
    use_vertex = os.getenv("ANTHROPIC_USE_VERTEX", "false").strip().lower() in {"1","true","yes"}
    if use_vertex:
        if ("-" in chosen) and ("@" not in chosen):
            try:
                base, date = chosen.rsplit("-", 1)
                if date.isdigit():
                    chosen = f"{base}@{date}"
            except Exception:
                pass
    return chosen

