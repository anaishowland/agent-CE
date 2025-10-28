"""
Map external MODEL identifiers to OpenAI Computer Use choices.

This module is intentionally small: we currently route through the Responses API
using the provided model string (e.g., "computer-use-preview"). If we later need
to alias or validate models, add that logic here.
"""

from typing import Final


# Default OpenAI Computer Use model
DEFAULT_OPENAI_CU_MODEL: Final[str] = "computer-use-preview"


def llm_config(model: str | None) -> str:
    if not model or not str(model).strip():
        return DEFAULT_OPENAI_CU_MODEL
    return str(model).strip()

