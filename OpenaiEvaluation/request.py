from __future__ import annotations

"""Minimal wrapper around OpenAI Responses API for Computer Use.

This module centralizes request assembly and client calls so the rest of the
agent code remains simple. It registers exactly one tool (browser computer use)
and provides helpers for initial and follow-up calls.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI
import os
import httpx
import logging
import time


_CLIENT: OpenAI | None = None


def _client() -> OpenAI:
    # Relies on environment variables for API key and base URL
    # OPENAI_API_KEY and optional OPENAI_BASE_URL
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI()
    return _CLIENT


def tool_spec(display_width: int = 1024, display_height: int = 768) -> List[Dict[str, Any]]:
    return [
        {
            "type": "computer_use_preview",
            "display_width": int(display_width),
            "display_height": int(display_height),
            "environment": "browser",
        }
    ]


def _http_responses_create(payload: Dict[str, Any]) -> Dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # Use Responses API header instead of Assistants; omit if unsupported
        "OpenAI-Beta": "responses=v1",
    }
    with httpx.Client(timeout=60.0) as client:
        last_resp: Optional[httpx.Response] = None
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = client.post(url, headers=headers, json=payload)
                last_resp = resp
            except httpx.TimeoutException as e:
                last_exc = e
                try:
                    logging.warning("[HTTP] /responses timeout on attempt %s", attempt + 1)
                except Exception:
                    pass
                time.sleep(1.0 * (2 ** attempt))
                continue

            # Retry on transient 5xx
            if 500 <= resp.status_code < 600:
                req_id = resp.headers.get("x-request-id")
                try:
                    logging.warning(
                        "[HTTP] /responses %s server error (attempt %s, request_id=%s): %s",
                        resp.status_code,
                        attempt + 1,
                        req_id,
                        resp.text,
                    )
                except Exception:
                    pass
                time.sleep(1.0 * (2 ** attempt))
                continue

            # Non-5xx: raise if 4xx and return body otherwise
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                req_id = resp.headers.get("x-request-id")
                try:
                    logging.error(
                        "[HTTP] /responses %s body (request_id=%s): %s",
                        resp.status_code,
                        req_id,
                        resp.text,
                    )
                except Exception:
                    pass
                raise
            return resp.json()

        # Give up after retries
        if last_resp is not None:
            last_resp.raise_for_status()  # will raise with context
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("/responses failed without response or exception")


def create_initial(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.0,
    display_width: int = 1024,
    display_height: int = 768,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "input": messages,
        "tools": tool_spec(display_width, display_height),
        "reasoning": {"summary": "concise"},
        "temperature": float(temperature),
        "truncation": "auto",
    }
    client = _client()
    try:
        responses = getattr(client, "responses")
        resp = responses.create(**payload)
        return resp.to_dict() if hasattr(resp, "to_dict") else resp  # type: ignore[return-value]
    except AttributeError:
        # Fallback to raw HTTP if this SDK version lacks `responses`
        return _http_responses_create(payload)


def create_followup(
    model: str,
    previous_response_id: str,
    input_items: List[Dict[str, Any]],
    temperature: float = 0.0,
    display_width: int = 1024,
    display_height: int = 768,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "previous_response_id": previous_response_id,
        "input": input_items,
        "tools": tool_spec(display_width, display_height),
        "reasoning": {"summary": "concise"},
        "temperature": float(temperature),
        "truncation": "auto",
    }
    client = _client()
    try:
        responses = getattr(client, "responses")
        resp = responses.create(**payload)
        return resp.to_dict() if hasattr(resp, "to_dict") else resp  # type: ignore[return-value]
    except AttributeError:
        return _http_responses_create(payload)


