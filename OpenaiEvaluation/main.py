"""OpenAI Computer Use Evaluation Module

Refactored to a small orchestrator that delegates the browser interaction loop
to `OpenaiEvaluation.loop.run_task`, uses `OpenaiEvaluation.request` for
Responses API calls, and `OpenaiEvaluation.storage` for artifact handling.

This mirrors the simplicity of the `cua-sdk` Docker loop while preserving the
standard agent interface used by other modules (Notte/Browseruse).
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Dict, Any
import logging
import json
import signal
import sys
from contextlib import suppress

from neurosim.evaluation import Evaluation
from neurosim.utils.models import EvaluationRequest, AgentResult, AgentErrors

from OpenaiEvaluation.llm import llm_config
from OpenaiEvaluation.urls import resolve_start_url
# Refactor imports for new modular loop
from OpenaiEvaluation.loop import run_task
from OpenaiEvaluation.prompt import system_text as build_system_prompt
from OpenaiEvaluation.storage import write_result_local, upload_artifacts_to_gcs
from playwright.async_api import async_playwright


class OpenaiEvaluation(Evaluation):
    agent_name: str
    agent_version: str

    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.agent_name = "OpenAI Computer Use"
        # Version is carried by the model/tool; we expose model string
        self.agent_version = llm_config(self.request.model)

    def get_llm(self) -> str:
        return llm_config(self.request.model)

    async def run(self) -> AgentResult:
        try:
            start_time = time.time()
            jobId = self.request.jobid
            taskId = self.request.taskid
            episode = self.request.episode
            user_id = self.request.userid
            task = self.request.task
            model_name = self.config.model

            # Configure logging
            log_level = os.getenv("LOG_LEVEL", "INFO").upper()
            try:
                logging.basicConfig(level=getattr(logging, log_level))
            except Exception:
                logging.basicConfig(level=logging.INFO)

            # Legacy inline HTTP helper removed in favor of OpenaiEvaluation.request

            # Legacy key helpers removed (centralized in OpenaiEvaluation/keys.py)

            async with async_playwright() as p:
                headless_env = os.getenv("HEADLESS", "0").strip().lower()
                is_headless = headless_env in {"1", "true", "yes"}
                launch_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--use-gl=swiftshader",
                    "--ozone-platform=x11",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
                if is_headless:
                    launch_args.insert(0, "--headless=new")
                browser = await p.chromium.launch(headless=is_headless, channel="chrome", args=launch_args)
                # Single source of truth for viewport; configurable via advanced_settings
                try:
                    vw = int(self.request.advanced_settings.get("display_width_px", 1024))
                except Exception:
                    vw = 1024
                try:
                    vh = int(self.request.advanced_settings.get("display_height_px", 768))
                except Exception:
                    vh = 768
                viewport = {"width": vw, "height": vh}
                context = await browser.new_context(viewport=viewport, ignore_https_errors=True, bypass_csp=True)
                page = await context.new_page()

                # Determine a sensible starting URL via helper
                start_url = resolve_start_url(task)
                logging.info("[RUN] jobId=%s taskId=%s episode=%s model=%s", jobId, taskId, episode, model_name)
                logging.info("[BROWSER] headless=%s", is_headless)
                # Unique run identifier to avoid overwrites in flat exports
                run_id = os.getenv("RUN_ID", time.strftime("%Y%m%d-%H%M%S"))
                # Navigation is handled once inside loop.run_task to avoid duplication.

                # Save artifacts locally under the same canonical layout as GCS
                screenshot_dir = os.path.join(str(user_id), str(jobId), str(episode), str(taskId))
                os.makedirs(screenshot_dir, exist_ok=True)

                # Minimal best-effort flush utility (local + GCS)
                def _best_effort_flush() -> None:
                    with suppress(Exception):
                        try:
                            obj: Dict[str, Any] = self.result.model_dump()  # type: ignore[attr-defined]
                        except Exception:
                            obj = self.result.dict()  # type: ignore[attr-defined]
                        write_result_local(obj, screenshot_dir)
                    with suppress(Exception):
                        upload_artifacts_to_gcs(
                            screenshot_dir, str(user_id), str(jobId), str(episode), str(taskId)
                        )

                # Trap SIGTERM/SIGINT to persist partial results before exit
                def _on_term(signum, frame):  # type: ignore[no-untyped-def]
                    try:
                        # Mark termination in result before flushing
                        self.result.success = False
                        self.result.results = "Terminated by signal"
                        with suppress(Exception):
                            self.result.latency = round(time.time() - start_time, 2)
                        with suppress(Exception):
                            self.result.error = AgentErrors(
                                name="Terminated", error=f"Received signal {signum}", traceback=""
                            )
                        # Ask loop to stop cooperatively
                        with suppress(Exception):
                            from OpenaiEvaluation.loop import request_stop  # local import to avoid cycles
                            request_stop()
                        _best_effort_flush()
                    except Exception:
                        pass
                    # Do not hard-exit; allow graceful finally block to run

                try:
                    signal.signal(signal.SIGTERM, _on_term)  # type: ignore[arg-type]
                    signal.signal(signal.SIGINT, _on_term)   # type: ignore[arg-type]
                except Exception:
                    pass

                # Refactored: delegate to loop.run_task
                try:
                    # Populate task metadata for parity with other agents
                    try:
                        self.result.task = {
                            "taskId": str(taskId),
                            "task": str(task),
                            "model": model_name,
                        }
                    except Exception:
                        pass

                    max_steps_cfg = int(self.request.advanced_settings.get("max_steps", 50))
                    temperature = float(self.request.advanced_settings.get("temperature", 0))
                    sys_prompt = build_system_prompt(os.getenv("OPENAI_SYSTEM_PROMPT"))

                    result_dict = await run_task(
                            page=page,
                            task_text=str(task),
                            model=str(model_name),
                            max_steps=max_steps_cfg,
                            temperature=temperature,
                            start_url=str(start_url),
                            screenshot_dir=str(screenshot_dir),
                            system_prompt=sys_prompt,
                            display_width=viewport["width"],
                            display_height=viewport["height"],
                        )

                    self.result.success = bool(result_dict.get("success", False))
                    self.result.results = str(result_dict.get("results", ""))
                    self.result.steps = list(result_dict.get("steps", []))
                    self.result.tokens = list(result_dict.get("tokens", []))
                    self.result.latency = round(time.time() - start_time, 2)
                except Exception as e:
                    self.result.success = False
                    self.result.results = "ERROR: OpenAI run failed"
                    import traceback as _tb
                    self.result.error = AgentErrors(
                        name=type(e).__name__, error=str(e), traceback=_tb.format_exc()
                    )
                finally:
                    # Always persist results (even on exceptions)
                    _best_effort_flush()
                    # Close browser context
                    try:
                        await context.close()
                    except Exception:
                        pass
                    try:
                        await browser.close()
                    except Exception:
                        pass  # pragma: no cover
                return self.result
        except Exception as e:  # pragma: no cover
            self.result.success = False
            self.result.results = "ERROR: OpenAI run failed"
            import traceback as _tb
            self.result.error = AgentErrors(
                name=type(e).__name__, error=str(e), traceback=_tb.format_exc()
            )
            # Best-effort: write partial result and upload any local screenshots if available
            try:
                obj: Dict[str, Any] = self.result.model_dump()  # type: ignore[attr-defined]
            except Exception:
                obj = self.result.dict()  # type: ignore[attr-defined]
            try:
                user_id = self.request.userid
                jobId = self.request.jobid
                episode = self.request.episode
                taskId = self.request.taskid
                screenshot_dir = os.path.join(str(user_id), str(jobId), str(episode), str(taskId))
                write_result_local(obj, screenshot_dir)
                upload_artifacts_to_gcs(screenshot_dir, str(user_id), str(jobId), str(episode), str(taskId))
            except Exception:
                pass
        return self.result

    def compute_steps(self) -> None:
        # Steps already include screenshot_path saved to the task folder; do not add extra fields
        return

    def compute_tokens(self) -> None:
        # Tokens were normalized in run(); nothing additional required here.
        return


if __name__ == "__main__":
    RunEvaluation = OpenaiEvaluation.from_cli()
    try:
        asyncio.run(asyncio.wait_for(RunEvaluation.execute(), timeout=1800))
    except asyncio.TimeoutError:
        import sys
        sys.exit(124)