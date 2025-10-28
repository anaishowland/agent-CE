import os
import re
import asyncio
import base64
import time
import json
import zstandard as zstd
from typing import List, Dict, Any, Optional, Tuple
import logging
import shutil
from pathlib import Path

from anthropic import Anthropic
try:
    from anthropic import AnthropicVertex  # type: ignore
except Exception:
    AnthropicVertex = None  # type: ignore
from playwright.async_api import async_playwright
from pydantic import BaseModel, PositiveFloat, Field

try:
    from neurosim.evaluation import Evaluation  # type: ignore
    from neurosim.utils.models import EvaluationRequest, AgentResult, AgentErrors  # type: ignore
    HAVE_NEUROSIM = True
except Exception:
    HAVE_NEUROSIM = False
    # Minimal fallbacks to allow local debug runs without neurosim
    from dataclasses import dataclass
    from pydantic import BaseModel
    @dataclass
    class EvaluationRequest:  # type: ignore
        userid: str
        model: str
        jobid: str
        task: str
        taskid: str
        episode: int
        advanced_settings: Dict[str, Any]
        bucket_name: str = ""
        pipeline: str = ""

    class _ConfigShim:
        def __init__(self, model: str, save_path: str):
            self.model = model
            self.save_path = save_path

    class AgentErrors(BaseModel):  # type: ignore
        name: str = ""
        traceback: str = ""
        error: str = ""

    class AgentResult(BaseModel):  # type: ignore
        jobId: str = ""
        success: bool = False
        latency: float = 0.0
        tokens: List[Dict[str, Any]] = []
        task: Dict[str, Any] = {}
        steps: List[Dict[str, Any]] = []
        results: str = ""
        error: Optional[Dict[str, Any]] = None

    class Evaluation:  # type: ignore
        def __init__(self, request: EvaluationRequest):
            self.request = request
            self.result = type("Result", (), {})()
            self.config = _ConfigShim(model=request.model, save_path=os.path.join(request.jobid, str(request.episode), str(request.taskid)))

        async def execute(self):
            os.makedirs(self.config.save_path, exist_ok=True)
            res = await self.run()
            # Write result.json for local debug runs
            try:
                out = getattr(res, "model_dump", None)
                if callable(out):
                    payload = out()
                elif isinstance(res, dict):
                    payload = res
                else:
                    payload = res.__dict__
            except Exception:
                payload = {}
            # Shape payload to match canonical order and keys
            try:
                allowed_keys = [
                    "jobId", "success", "latency", "tokens", "task", "steps", "results", "error",
                ]
                shaped = {k: payload.get(k) for k in allowed_keys if k in payload}
                # Write human-readable JSON for debug; canonical artifact is result.zst
                with open(os.path.join(self.config.save_path, "result.json"), "w") as f:
                    json.dump(shaped, f, indent=2)
            except Exception:
                with open(os.path.join(self.config.save_path, "result.json"), "w") as f:
                    json.dump(payload, f, indent=2)

        @classmethod
        def from_cli(cls):  # very small CLI shim
            import argparse as _argparse
            parser = _argparse.ArgumentParser()
            parser.add_argument("--jobId", required=True)
            parser.add_argument("--task", required=True)
            # Accept both --taskid and --taskId for parity with OpenAI CLI
            parser.add_argument("--taskid", required=False)
            parser.add_argument("--taskId", required=False)
            parser.add_argument("--user", required=True)
            parser.add_argument("--episode", required=True, type=int)
            parser.add_argument("--model", required=True)
            parser.add_argument("--advanced_settings", required=False, type=json.loads, default={})
            args = parser.parse_args()
            _taskid = args.taskid or args.taskId
            if not _taskid:
                raise SystemExit("--taskId (or --taskid) is required")
            req = EvaluationRequest(
                userid=args.user,
                model=args.model,
                jobid=args.jobId,
                task=args.task,
                taskid=_taskid,
                episode=args.episode,
                advanced_settings=args.advanced_settings or {},
            )
            return cls(req)

from .llm import get_llm_model


class TokenInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StepState(BaseModel):
    previous_goal_status: str = ""
    previous_goal_eval: str = ""
    page_summary: str = ""
    relevant_interactions: List[Any] = Field(default_factory=list)
    memory: str = ""
    next_goal: str = ""


class StepAction(BaseModel):
    type: str = ""
    # Common click/mouse fields
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    # Scroll deltas when applicable
    dx: Optional[int] = None
    dy: Optional[int] = None
    # Key/type payloads when applicable
    key: Optional[str] = None
    text: Optional[str] = None


class Step(BaseModel):
    state: StepState = StepState()
    action: StepAction = StepAction()
    screenshot_path: str = ""

class AnthropicEvaluation(Evaluation):
    """Claude Computer Use Evaluation matching Notte/Browser Use pattern."""

    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.agent_name = "Anthropic Computer Use"
        self.agent_version = get_llm_model(self.request.model)
        # Default to direct Anthropic API key; enable Vertex only if ANTHROPIC_USE_VERTEX=true
        use_vertex = os.getenv("ANTHROPIC_USE_VERTEX", "false").strip().lower() in {"1","true","yes"}
        if use_vertex:
            if AnthropicVertex is None:
                raise RuntimeError("AnthropicVertex client not available. Ensure anthropic[vertex] is installed.")
            region = os.getenv("ANTHROPIC_VERTEX_REGION", os.getenv("VERTEX_REGION", "global"))
            project = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("GCP_PROJECT", ""))
            self.client = AnthropicVertex(region=region, project_id=project)
        else:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            try:
                self.client = Anthropic(api_key=api_key, max_retries=2, timeout=60)
            except Exception:
                self.client = Anthropic(api_key=api_key)
        # Configure logging level
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        try:
            logging.basicConfig(level=getattr(logging, log_level))
        except Exception:
            logging.basicConfig(level=logging.INFO)

    def get_llm(self) -> str:
        return get_llm_model(self.request.model)

    @staticmethod
    def _placeholder_b64() -> str:
        # 1x1 transparent PNG
        return (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wwAAgMBgQd8r3QAAAAASUVORK5CYII="
        )

    @staticmethod
    def _convert_key_name(raw: str) -> str:
        mapping = {
            "enter": "Enter", "return": "Enter",
            "esc": "Escape", "escape": "Escape",
            "tab": "Tab", "space": "Space",
            "backspace": "Backspace",
            "delete": "Delete", "insert": "Insert",
            "home": "Home", "end": "End",
            "pagedown": "PageDown", "page_down": "PageDown",
            "pageup": "PageUp", "page_up": "PageUp",
            "up": "ArrowUp", "down": "ArrowDown",
            "left": "ArrowLeft", "right": "ArrowRight",
            "shift": "Shift", "ctrl": "Control",
            "control": "Control", "alt": "Alt",
        }
        s = (raw or "").strip()
        if not s:
            return ""
        key_lower = s.lower().replace("_", "")
        return mapping.get(key_lower, s.title())

    async def _take_screenshot(self, page, step_num: int) -> str:
        path = os.path.join(self.config.save_path, f"screenshot_{step_num}.png")
        await page.screenshot(path=path)
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    async def _execute_action(self, *, page, action: str, step_num: int, current_coords: List[int], **kwargs) -> Tuple[Dict[str, Any], List[int]]:
        result = {"success": False, "output": "", "base64_image": ""}
        try:
            if action == "screenshot":
                b64 = await self._take_screenshot(page, step_num)
                result.update(success=True, output="Screenshot taken", base64_image=b64)
            elif action in [
                "left_click", "mouse_click", "click", "right_click", "middle_click",
                "double_click", "triple_click", "left_mouse_down", "left_mouse_up", "left_click_drag"
            ]:
                coordinates = kwargs.get("coordinate", None)
                if coordinates:
                    if isinstance(coordinates, dict):
                        x, y = coordinates.get("x", 0), coordinates.get("y", 0)
                    elif isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                        x, y = coordinates
                    else:
                        x, y = current_coords
                else:
                    x, y = current_coords
                bx, by = int(x), int(y)
                if bx < 0 or by < 0:
                    result.update(success=False, output=f"Error: Coordinates ({bx},{by}) are negative.")
                    return result, current_coords
                btn = "left"
                if action == "right_click":
                    btn = "right"
                if action == "middle_click":
                    btn = "middle"
                if action == "double_click":
                    await page.mouse.dblclick(bx, by)
                    current_coords = [bx, by]
                    result.update(success=True, output=f"Double clicked at ({bx}, {by})")
                elif action == "triple_click":
                    await page.mouse.click(bx, by, click_count=3, button=btn)
                    current_coords = [bx, by]
                    result.update(success=True, output=f"Triple clicked at ({bx}, {by})")
                elif action == "left_mouse_down":
                    await page.mouse.move(bx, by)
                    await page.mouse.down(button="left")
                    current_coords = [bx, by]
                    result.update(success=True, output=f"Mouse down at ({bx}, {by})")
                elif action == "left_mouse_up":
                    await page.mouse.up(button="left")
                    result.update(success=True, output="Mouse up")
                elif action == "left_click_drag":
                    start = kwargs.get("coordinate_start") or coordinates
                    end = kwargs.get("coordinate_end")
                    if (
                        start and end and isinstance(start, (list, tuple)) and isinstance(end, (list, tuple))
                        and len(start) == 2 and len(end) == 2
                    ):
                        sx, sy = int(start[0]), int(start[1])
                        ex, ey = int(end[0]), int(end[1])
                        await page.mouse.move(sx, sy)
                        await page.mouse.down(button="left")
                        await page.mouse.move(ex, ey)
                        await page.mouse.up(button="left")
                        current_coords = [ex, ey]
                        result.update(success=True, output=f"Dragged from ({sx},{sy}) to ({ex},{ey})")
                    else:
                        result.update(success=False, output="Error: left_click_drag requires coordinate_start and coordinate_end [x,y]")
                else:
                    await page.mouse.click(bx, by, button=btn)
                    current_coords = [bx, by]
                    result.update(success=True, output=f"Clicked ({btn}) at ({bx}, {by})")
            elif action == "mouse_move":
                coordinates = kwargs.get("coordinate", None)
                if coordinates:
                    if isinstance(coordinates, dict):
                        x, y = coordinates.get("x", 0), coordinates.get("y", 0)
                    elif isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                        x, y = coordinates
                    else:
                        x, y = current_coords
                else:
                    x, y = current_coords
                await page.mouse.move(int(x), int(y))
                current_coords = [int(x), int(y)]
                result.update(success=True, output=f"Moved mouse to ({x}, {y})")
            elif action == "hover":
                coordinates = kwargs.get("coordinate", None)
                if coordinates:
                    if isinstance(coordinates, dict):
                        x, y = coordinates.get("x", 0), coordinates.get("y", 0)
                    elif isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                        x, y = coordinates
                    else:
                        x, y = current_coords
                else:
                    x, y = current_coords
                await page.mouse.move(int(x), int(y))
                current_coords = [int(x), int(y)]
                result.update(success=True, output=f"Hovered at ({x}, {y})")
            elif action == "scroll":
                direction = (kwargs.get("scroll_direction") or "down").lower()
                amount = int(kwargs.get("scroll_amount", 3))
                dx, dy = 0, 0
                if "coordinate" in kwargs and isinstance(kwargs.get("coordinate"), (list, tuple)) and len(kwargs.get("coordinate")) == 2:
                    dx, dy = int(kwargs["coordinate"][0]), int(kwargs["coordinate"][1])
                else:
                    if direction in {"down", "up"}:
                        dy = 100 * amount if direction == "down" else -100 * amount
                    elif direction in {"right", "left"}:
                        dx = 100 * amount if direction == "right" else -100 * amount
                await page.mouse.wheel(dx, dy)
                result.update(success=True, output=f"Scrolled dx={dx} dy={dy}")
            elif action == "key":
                key_input = str(kwargs.get("key", "") or kwargs.get("text", ""))
                allowed_base = {
                    "Enter","Escape","Tab","Space","Backspace","Delete","Insert","Home","End",
                    "PageDown","PageUp","ArrowUp","ArrowDown","ArrowLeft","ArrowRight",
                    "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12",
                }
                allowed_mods = {"Control","Alt","Shift"}
                blocked_os_keys = {"Meta","Super","Command","Cmd","Win","Windows","MetaL","MetaR","SuperL","SuperR"}

                def convert_key(k: str) -> str:
                    k_norm = (k or "").strip()
                    k_lower = k_norm.lower().replace("_", "")
                    if k_norm in blocked_os_keys or k_norm.title() in blocked_os_keys or k_lower in {s.lower() for s in blocked_os_keys}:
                        return ""
                    # Use local converter to avoid dependency on external Evaluation
                    mapping = {
                        "enter": "Enter", "return": "Enter",
                        "esc": "Escape", "escape": "Escape",
                        "tab": "Tab", "space": "Space",
                        "backspace": "Backspace",
                        "delete": "Delete", "insert": "Insert",
                        "home": "Home", "end": "End",
                        "pagedown": "PageDown", "page_down": "PageDown",
                        "pageup": "PageUp", "page_up": "PageUp",
                        "up": "ArrowUp", "down": "ArrowDown",
                        "left": "ArrowLeft", "right": "ArrowRight",
                        "shift": "Shift", "ctrl": "Control", "control": "Control", "alt": "Alt",
                    }
                    return mapping.get(k_lower, k_norm.title())

                def is_allowed_standalone(k: str) -> bool:
                    return k in allowed_base or k in allowed_mods

                def is_allowed_combo_key(k: str) -> bool:
                    # Allow letters/digits in combos (e.g., Control+L)
                    return k in allowed_base or k in allowed_mods or (len(k) == 1 and k.isalnum())

                if "+" in key_input:
                    keys_raw = [seg.strip() for seg in key_input.split("+")]
                    keys = [convert_key(seg) for seg in keys_raw]
                    if any(not k for k in keys) or any(not is_allowed_combo_key(k) for k in keys):
                        result.update(success=False, output=f"Blocked or unknown hotkey: {key_input}")
                    else:
                        await page.keyboard.down(keys[0])
                        for k in keys[1:]:
                            await page.keyboard.down(k)
                        for k in reversed(keys):
                            await page.keyboard.up(k)
                        result.update(success=True, output=f"Pressed hotkey: {'+'.join(keys)}")
                elif " " in key_input:
                    keys_raw = [seg.strip() for seg in key_input.split()]
                    keys = [convert_key(seg) for seg in keys_raw]
                    if any(not k for k in keys) or any(not is_allowed_standalone(k) and not (len(k)==1 and k.isalnum()) for k in keys):
                        result.update(success=False, output=f"Blocked or unknown keys: {' '.join(keys_raw)}")
                    else:
                        for k in keys:
                            await page.keyboard.press(k)
                        result.update(success=True, output="Pressed keys: {}".format(" ".join(keys)))
                else:
                    k = convert_key(key_input.strip())
                    if not k or not (is_allowed_standalone(k) or (len(k)==1 and k.isalnum())):
                        result.update(success=False, output=f"Blocked or unknown key: {key_input}")
                    else:
                        await page.keyboard.press(k)
                        result.update(success=True, output=f"Pressed key: {k}")
            elif action == "type":
                text = kwargs.get("text", "")
                await page.keyboard.type(str(text), delay=50)
                result.update(success=True, output=f"Typed: {text}")
            elif action == "open_url":
                raw = str(kwargs.get("url", "")).strip()
                if not raw:
                    result.update(success=False, output="Error: open_url requires 'url'")
                    return result, current_coords
                url = raw if raw.startswith("http://") or raw.startswith("https://") else f"https://{raw}"
                wait_strategies = ["load", "domcontentloaded", "networkidle"]
                nav_ok = False
                for strategy in wait_strategies:
                    try:
                        await page.goto(url, wait_until=strategy, timeout=60000)
                        nav_ok = True
                        break
                    except Exception:
                        continue
                if nav_ok:
                    result.update(success=True, output=f"Navigated to {url}")
                else:
                    result.update(success=False, output=f"Error: failed to navigate to {url}")
            elif action == "hold_key":
                combo = str(kwargs.get("key", "")).strip()
                if not combo:
                    result.update(success=False, output="Error: hold_key requires 'key'")
                else:
                    keys = [self._convert_key_name(k.strip()) for k in combo.split("+")]
                    for k in keys:
                        await page.keyboard.down(k)
                    result.update(success=True, output=f"Holding keys: {'+'.join(keys)}")
            elif action == "wait":
                sec = float(kwargs.get("seconds", kwargs.get("duration", 1)))
                await page.wait_for_timeout(int(sec * 1000))
                result.update(success=True, output=f"Waited {sec:.2f}s")
        except Exception as e:
            result["output"] = f"Error executing {action}: {e}"
        return result, current_coords

    def _extract_url_from_task(self, task_prompt: str) -> str:
        try:
            match = re.search(r"https?://[^\s)]+", task_prompt)
            if match:
                return match.group(0)
        except Exception:
            pass
        return ""

    def _infer_start_url(self, task_prompt: str) -> str:
        """When no URL is provided or detected, start on a neutral search page.
        This avoids biasing toward any target site while giving the agent a UI to navigate.
        """
        return "https://www.google.com/"

    async def _llm_pick_start_url(self, task_prompt: str) -> str:
        """Ask the LLM for a single https:// URL to start from based on the task.
        Falls back to Google if parsing fails.
        """
        try:
            prompt = (
                "Only output a single preferred website URL appropriate for this user intent: '"
                + (task_prompt or "").strip()
                + "'. Do not include any extra words or punctuation—just exactly the URL with 'https://' prefix."
            )
            # Run the synchronous client on a worker thread to avoid blocking the event loop
            resp = await asyncio.to_thread(
                self.client.messages.create,
                model=self.config.model,
                max_tokens=32,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            # Try to read content blocks
            candidate = ""
            try:
                for blk in getattr(resp, "content", []) or []:
                    if getattr(blk, "type", "") == "text" and getattr(blk, "text", ""):
                        candidate = (blk.text or "").strip()
                        break
            except Exception:
                candidate = ""
            # Fallbacks
            if not candidate and hasattr(resp, "completion") and isinstance(resp.completion, str):
                candidate = resp.completion.strip().split()[0]
            if candidate and candidate.startswith("https://"):
                # Normalize to site homepage (scheme + host), avoid deep links
                try:
                    from urllib.parse import urlparse
                    u = urlparse(candidate)
                    if u.scheme and u.netloc:
                        return f"{u.scheme}://{u.netloc}/"
                except Exception:
                    return candidate
        except Exception:
            pass
        return "https://www.google.com/"

    async def run(self) -> AgentResult:
        current_coords: List[int] = [0, 0]
        steps: List[Step] = []
        steps_diagnostics: List[Dict[str, Any]] = []
        success = True
        error_msg = ""
        tokens: List[TokenInfo] = []
        start_ts = time.time()
        last_text: str = ""

        async with async_playwright() as p:
            headless_env = os.getenv("HEADLESS", "0").strip().lower()
            headless_flag = headless_env in {"1", "true", "yes"}
            logging.info("[ENV] HEADLESS=%s → headless_flag=%s", headless_env, headless_flag)
            logging.info("[ENV] DISPLAY=%s", os.getenv("DISPLAY", "<unset>"))
            logging.info("[ENV] ANTHROPIC_TOOL_VERSION=%s", os.getenv("ANTHROPIC_TOOL_VERSION", "computer_20250124"))
            logging.info("[ENV] ANTHROPIC_BETA_VERSION=%s", os.getenv("ANTHROPIC_BETA_VERSION", "computer-use-2025-01-24"))
            logging.info("[RUN] jobId=%s taskId=%s episode=%s model=%s", self.request.jobid, self.request.taskid, self.request.episode, self.config.model)
            # Best-effort Chrome version diagnostics
            try:
                chrome_bin = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or "<not found>"
                logging.info("[CHROME] binary=%s", chrome_bin)
                if chrome_bin and chrome_bin != "<not found>":
                    ver = os.popen(f"{chrome_bin} --version").read().strip()
                    logging.info("[CHROME] version=%s", ver)
            except Exception as e:
                logging.debug("[CHROME] version check failed: %s", e)
            launch_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-gpu",
                "--use-gl=swiftshader",
                "--ozone-platform=x11",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            if headless_flag:
                launch_args.insert(0, "--headless=new")
            # Use Chrome channel installed by Playwright (Chrome for Testing), matching other agents
            logging.info("[PLAYWRIGHT] launching chromium channel=chrome headless=%s args=%s", headless_flag, launch_args)
            try:
                browser = await p.chromium.launch(
                    headless=headless_flag,
                    channel="chrome",
                    args=launch_args,
                )
            except Exception as e:
                logging.exception("[PLAYWRIGHT] launch failed: %s", e)
                # Extra diagnostics
                logging.error("[DIAG] DISPLAY=%s", os.getenv("DISPLAY", "<unset>"))
                logging.error("[DIAG] HEADLESS=%s", headless_env)
                try:
                    import shutil as _sh
                    logging.error("[DIAG] google-chrome path: %s", _sh.which("google-chrome"))
                except Exception:
                    pass
                raise
            logging.info("[PLAYWRIGHT] browser launched OK")
            # Viewport size can be overridden via advanced_settings: display_width_px/display_height_px
            try:
                _vw = int(self.request.advanced_settings.get("display_width_px", 1024))
            except Exception:
                _vw = 1024
            try:
                _vh = int(self.request.advanced_settings.get("display_height_px", 768))
            except Exception:
                _vh = 768
            context = await browser.new_context(viewport={"width": _vw, "height": _vh})
            page = await context.new_page()
            logging.info("[PLAYWRIGHT] page created; navigating to start_url shortly")

            start_url = os.getenv("START_URL", "").strip() or self._extract_url_from_task(self.request.task)
            if not start_url:
                try:
                    logging.info("[NAV] obtain start_url via _llm_pick_start_url (10s timeout)")
                    start_url = await asyncio.wait_for(self._llm_pick_start_url(self.request.task), timeout=10)
                except Exception as e:
                    logging.warning("[NAV] _llm_pick_start_url failed: %s; fallback to %s", e, self._infer_start_url(self.request.task))
                    start_url = self._infer_start_url(self.request.task)
            logging.info("[NAV] start_url=%s", start_url or "<none>")
            if start_url:
                wait_strategies = ["load", "domcontentloaded", "networkidle"]
                for strategy in wait_strategies:
                    try:
                        logging.info("[NAV] goto %s wait_until=%s", start_url, strategy)
                        await page.goto(start_url, wait_until=strategy, timeout=60000)
                        break
                    except Exception:
                        if strategy == wait_strategies[-1]:
                            logging.warning("[NAV] all wait strategies failed for %s", start_url)
                        else:
                            logging.info("[NAV] retrying with next strategy after failure")
                try:
                    await page.wait_for_selector("body", state="visible", timeout=5000)
                except Exception:
                    logging.debug("[NAV] body visible wait skipped/failed")
                try:
                    await page.wait_for_timeout(1000)
                except Exception:
                    logging.debug("[NAV] settle sleep skipped/failed")
            try:
                await page.wait_for_timeout(500)
            except Exception:
                logging.debug("[NAV] initial settle sleep skipped/failed")

            # Initial screenshot with fallback to placeholder
            try:
                last_screenshot_b64 = await self._take_screenshot(page, 0)
            except Exception:
                last_screenshot_b64 = ""
            if not last_screenshot_b64:
                last_screenshot_b64 = self._placeholder_b64()

            system_prompt = f"""
You control a single browser tab using the computer tool.

RULES:
- If the task text includes a URL, call open_url(url) FIRST.
- If the task text restricts to a specific domain (e.g., "Only use redfin.com"), stay on that domain.
- If no URL is present, call open_url to an appropriate start page for the task. If unsure, use https://www.google.com/.
- Use only page-level inputs: left_click, mouse_move, hover, scroll, key, type, screenshot. Do not use OS-level keys.


Follow the task strictly: {self.request.task}.
When viewing a page, scroll to see all content before deciding something isn't available.
Terminate when the task is complete, when you have reached the maximum number of steps, or when you encounter a CAPTCHA/Cloudflare or network security block. 
Do not ask the user for help.
After each action, take a screenshot and evaluate if you achieved the intended outcome. Explicitly show your thinking: "I have evaluated step X..." If not correct, try again.
            """
            messages: List[Dict[str, Any]] = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": (last_screenshot_b64 or self._placeholder_b64())}},
                ],
            }]

            last_step_num = 0
            hit_max_steps = False
            max_steps = int(self.request.advanced_settings.get("max_steps", os.getenv("MAX_STEPS", "0") or 50))
            # Anti-stuck tracking: detect repeated identical actions
            last_action_signature: Optional[Tuple[Any, Any, Any, Any]] = None
            repeated_same_action_count: int = 0
            for step_num in range(1, max_steps + 1):
                step_start_time = time.time()
                tool_version = os.getenv("ANTHROPIC_TOOL_VERSION", "computer_20250124")
                beta_version = os.getenv("ANTHROPIC_BETA_VERSION", "computer-use-2025-01-24")
                # Expose both the computer tool and a small custom open_url tool
                # Tool display size can also be overridden via the same advanced_settings keys
                _tw = _vw
                _th = _vh
                tools_def = [
                    {
                        "type": tool_version,
                        "name": "computer",
                        "display_width_px": int(_tw),
                        "display_height_px": int(_th),
                    },
                    {
                        "name": "open_url",
                        "description": "Open the given URL in the existing Chrome (Playwright) window and return a screenshot.",
                        "input_schema": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                        },
                    },
                ]

                # Minimal retry/backoff on API errors (e.g., 429)
                response = None
                last_err: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        response = await asyncio.to_thread(
                            self.client.messages.create,
                            model=self.config.model,
                            max_tokens=1024,
                            temperature=0,
                            messages=messages,
                            tools=tools_def,
                            extra_headers={"anthropic-beta": beta_version},
                        )
                        break
                    except Exception as e:
                        last_err = e
                        err_str = str(e).lower()
                        if ("429" in err_str) or ("rate limit" in err_str) or ("too many requests" in err_str) or ("timeout" in err_str):
                            backoff = 2 + attempt * 3
                            logging.warning("[ANTHROPIC] transient error, retrying in %ss (attempt %s/3): %s", backoff, attempt + 1, e)
                            try:
                                await asyncio.sleep(backoff)
                            except Exception:
                                pass
                            continue
                        else:
                            logging.exception("[ANTHROPIC] non-retryable error: %s", e)
                            raise
                if response is None and last_err is not None:
                    raise last_err
                logging.debug("[ANTHROPIC] response received with %d blocks", len(getattr(response, 'content', []) or []))

                # Per-step token accounting: record usage for each API call
                try:
                    usage = getattr(response, "usage", None)
                    if usage is not None:
                        tokens.append(TokenInfo(
                            prompt_tokens=getattr(usage, 'input_tokens', 0),
                            completion_tokens=getattr(usage, 'output_tokens', 0),
                            total_tokens=(getattr(usage, 'input_tokens', 0) + getattr(usage, 'output_tokens', 0))
                        ))
                except Exception:
                    pass

                assistant_content = []
                tool_uses = []
                step_texts = []
                for block in response.content:
                    if block.type == "text":
                        if block.text:
                            step_texts.append(block.text)
                            last_text = block.text
                        assistant_content.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        tool_uses.append(block)
                        assistant_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
                messages.append({"role": "assistant", "content": assistant_content})
                last_step_num = step_num

                if not tool_uses:
                    final_text = "\n".join(step_texts).strip()
                    # Treat known verification/captcha/network blockers as failure
                    # Inline blocker detection (avoid forward-ref before helper is defined below)
                    triggers = [
                        "captcha", "security verification", "cloudflare", "verifying you are human",
                        "verify you are human", "human verification", "i am not a robot", "access denied",
                        "network security block", "connectivity problem", "network error", "robot check",
                    ]
                    ft = (final_text or "").lower()
                    is_blocker = bool(final_text) and any(t in ft for t in triggers)

                    if final_text and not is_blocker:
                        logging.info("[STEP %s] completion without tool use", step_num)
                        last_screenshot_b64 = await self._take_screenshot(page, step_num)
                        steps.append(Step(
                            state=StepState(
                                previous_goal_status="success",
                                previous_goal_eval="Completed",
                                page_summary=final_text,
                                relevant_interactions=[],
                                memory="",
                                next_goal="",
                            ),
                            action=StepAction(type="screenshot"),
                            screenshot_path=os.path.join(self.config.save_path, f"screenshot_{step_num}.png").replace("\\", "/")
                        ))
                        last_text = final_text
                        success = True
                    else:
                        success = False
                        error_msg = "Captcha/verification or no final answer"
                    step_end_time = time.time()
                    steps_diagnostics.append({
                        "model_output": {
                            "evaluation_previous_goal": steps[-1].state.previous_goal_eval if steps else "",
                            "memory": "",
                            "next_goal": "",
                            "action": [],
                            "thinking": final_text,
                        },
                        "result": [{
                            "is_done": success,
                            "success": success,
                            "extracted_content": final_text,
                            "include_extracted_content_only_once": False,
                            "include_in_memory": False,
                        }],
                        "metadata": {
                            "step_start_time": step_start_time,
                            "step_end_time": step_end_time,
                            "step_number": step_num,
                        },
                    })
                    break

                tool_result_blocks = []
                screenshot_blocks = []
                screenshot_saved_this_step = False
                collected_actions: List[Dict[str, Any]] = []
                step_results: List[Dict[str, Any]] = []
                # Track the primary action signature for this step (action, x, y, text/url)
                step_action_signature: Optional[Tuple[Any, Any, Any, Any]] = None
                # CAPTCHA/human verification detection helpers
                def _is_captcha_text(texts: List[str]) -> bool:
                    joined = " ".join((t or "").lower() for t in texts)
                    trigger_phrases = [
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
                        "robot check",
                        "i cannot complete the task"
                    ]
                    return any(tok in joined for tok in trigger_phrases)

                def _is_captcha_result(output: str) -> bool:
                    val = (output or "").lower()
                    trigger_phrases = [
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
                        "robot check",
                    ]
                    return any(s in val for s in trigger_phrases)

                if _is_captcha_text(step_texts):
                    success = False
                    error_msg = "Captcha or human verification encountered"
                    logging.warning("[STEP %s] CAPTCHA detected in model text; stopping.", step_num)
                    break

                for tool_block in tool_uses:
                    # Determine action name (custom tool vs computer tool)
                    action_name = tool_block.input.get("action") if hasattr(tool_block, "input") else None
                    if getattr(tool_block, "name", "") == "open_url":
                        action_name = "open_url"

                    # Avoid passing duplicate 'action' key via kwargs
                    _input_payload = dict((tool_block.input or {}))
                    if "action" in _input_payload:
                        _input_payload.pop("action", None)
                    tool_result, current_coords = await self._execute_action(
                        page=page,
                        step_num=step_num,
                        current_coords=current_coords,
                        action=action_name or "",
                        **_input_payload,
                    )
                    logging.debug("[STEP %s] action=%s success=%s", step_num, tool_block.input.get("action"), tool_result.get("success"))
                    if tool_block.input.get("action") == "screenshot":
                        screenshot_saved_this_step = True
                        new_b64 = tool_result.get("base64_image") or ""
                        effective_b64 = new_b64 or (last_screenshot_b64 or self._placeholder_b64())
                        last_screenshot_b64 = effective_b64
                        screenshot_blocks.append({
                            "role": "user",
                            "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": effective_b64}}]
                        })
                    # CAPTCHA detection in tool results
                    if _is_captcha_result(tool_result.get("output") or ""):
                        success = False
                        error_msg = "Captcha or human verification encountered"
                        logging.warning("[STEP %s] CAPTCHA detected in tool result; stopping.", step_num)
                    tool_result_blocks.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "is_error": (not tool_result.get("success", False)),
                        "content": [{"type": "text", "text": tool_result.get("output") or "OK"}],
                    })
                    collected_actions.append({tool_block.name or "computer": tool_block.input})
                    step_results.append({
                        "is_done": False,
                        "long_term_memory": tool_result.get("output") or "",
                        "extracted_content": tool_result.get("output") or "",
                        "include_extracted_content_only_once": False,
                        "include_in_memory": True,
                    })

                    action_name = action_name or tool_block.input.get("action", "")
                    action_dict: Dict[str, Any] = {"type": action_name}
                    # Click-like actions → include x, y, button
                    if action_name in {"left_click", "mouse_click", "click", "right_click", "middle_click", "double_click", "triple_click", "left_mouse_down", "left_mouse_up", "left_click_drag"}:
                        coord = tool_block.input.get("coordinate")
                        if isinstance(coord, dict):
                            action_dict["x"] = int(coord.get("x", 0))
                            action_dict["y"] = int(coord.get("y", 0))
                        elif isinstance(coord, (list, tuple)) and len(coord) == 2:
                            action_dict["x"] = int(coord[0])
                            action_dict["y"] = int(coord[1])
                        # Infer button from action name
                        if action_name == "right_click":
                            action_dict["button"] = "right"
                        elif action_name == "middle_click":
                            action_dict["button"] = "middle"
                        else:
                            action_dict["button"] = "left"
                    # Scroll → include dx, dy
                    if action_name == "scroll":
                        dx, dy = 0, 0
                        coord = tool_block.input.get("coordinate")
                        if isinstance(coord, (list, tuple)) and len(coord) == 2:
                            dx, dy = int(coord[0]), int(coord[1])
                        else:
                            direction = str(tool_block.input.get("scroll_direction", "down")).lower()
                            amount = int(tool_block.input.get("scroll_amount", 3))
                            if direction in {"down", "up"}:
                                dy = 100 * amount if direction == "down" else -100 * amount
                            elif direction in {"right", "left"}:
                                dx = 100 * amount if direction == "right" else -100 * amount
                        action_dict["dx"] = dx
                        action_dict["dy"] = dy
                    # Key → include key; Type → include text
                    if action_name == "key":
                        if "key" in tool_block.input:
                            action_dict["key"] = str(tool_block.input.get("key") or "")
                        elif "text" in tool_block.input:
                            action_dict["key"] = str(tool_block.input.get("text") or "")
                    if action_name == "type":
                        action_dict["text"] = str(tool_block.input.get("text") or "")
                    if action_name == "open_url":
                        # Record the URL in text field for traceability
                        action_dict["text"] = str(tool_block.input.get("url") or "")
                    summary = "\n".join(step_texts) if step_texts else (
                        f"Executed {tool_block.input.get('action','')}" if tool_block and tool_block.input else ""
                    )
                    state = StepState(
                        previous_goal_status="success" if tool_result.get("success") else "failure",
                        previous_goal_eval=tool_result.get("output") or "",
                        page_summary=summary,
                        relevant_interactions=[],
                        memory=tool_result.get("output") or "",
                        next_goal="",
                    )
                    screenshot_path = os.path.join(self.config.save_path, f"screenshot_{step_num}.png") if tool_block.input.get("action") == "screenshot" else ""
                    steps.append(Step(state=state, action=StepAction(**action_dict), screenshot_path=screenshot_path.replace("\\", "/")))
                    # Update step action signature based on the last executed tool action
                    try:
                        ax = action_dict.get("x") if isinstance(action_dict, dict) else None
                        ay = action_dict.get("y") if isinstance(action_dict, dict) else None
                        at = action_dict.get("text") if isinstance(action_dict, dict) else None
                        an = (action_dict.get("type") or "").lower() if isinstance(action_dict, dict) else ""
                        step_action_signature = (an, ax, ay, at)
                    except Exception:
                        step_action_signature = step_action_signature or None

                if tool_result_blocks:
                    messages.append({"role": "user", "content": tool_result_blocks})
                for s in screenshot_blocks:
                    messages.append(s)
                if not screenshot_saved_this_step:
                    try:
                        new_b64 = await self._take_screenshot(page, step_num)
                    except Exception:
                        new_b64 = ""
                    effective_b64 = new_b64 or (last_screenshot_b64 or self._placeholder_b64())
                    last_screenshot_b64 = effective_b64
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": effective_b64}
                        }]
                    })

                # Keep only the latest screenshot in context to avoid N+1 image accumulation
                try:
                    # Identify the newest message that contains an image block
                    last_image_idx = None
                    for idx in range(len(messages) - 1, -1, -1):
                        try:
                            content_list = messages[idx].get("content", [])
                            if any((isinstance(c, dict) and c.get("type") == "image") for c in (content_list or [])):
                                last_image_idx = idx
                                break
                        except Exception:
                            continue
                    if last_image_idx is not None:
                        for idx, msg in enumerate(messages):
                            if idx == last_image_idx:
                                continue
                            try:
                                if isinstance(msg.get("content"), list):
                                    filtered = [
                                        c for c in msg["content"]
                                        if not (isinstance(c, dict) and c.get("type") == "image")
                                    ]
                                    msg["content"] = filtered
                                    # Drop messages that became empty after stripping images
                                    if not msg["content"]:
                                        # Mark for deletion by setting to None; prune below to avoid index shift
                                        messages[idx] = None  # type: ignore[assignment]
                            except Exception:
                                continue
                        # Prune any None placeholders (empty content messages removed)
                        messages[:] = [m for m in messages if m is not None]
                except Exception:
                    pass

                # Anti-stuck: if the same action has been attempted 3 times in a row, insert a re-evaluation hint
                try:
                    if step_action_signature is not None:
                        if last_action_signature is not None and step_action_signature == last_action_signature:
                            repeated_same_action_count += 1
                        else:
                            repeated_same_action_count = 1
                        last_action_signature = step_action_signature
                    # On third consecutive identical action, nudge the model to reconsider plan
                    if repeated_same_action_count >= 3:
                        try:
                            an, ax, ay, at = last_action_signature or ("", None, None, None)
                            hint = (
                                f"Observation: The previous action '{an}' "
                                + (f"at ({ax},{ay}) " if ax is not None and ay is not None else "")
                                + "was attempted multiple times without progress. Re-evaluate the plan and try a different approach (e.g., small scroll, open link in same tab, or navigate via another visible link)."
                            )
                        except Exception:
                            hint = "Observation: The previous action was attempted multiple times without progress. Re-evaluate the plan and try a different approach."
                        messages.append({
                            "role": "user",
                            "content": [{"type": "text", "text": hint}]
                        })
                        # Reset counter to avoid spamming the same hint
                        repeated_same_action_count = 0
                except Exception:
                    pass

                step_end_time = time.time()
                # Keep diagnostics in-memory only; do not persist in final artifact
                steps_diagnostics.append({
                    "model_output": {
                        "evaluation_previous_goal": steps[-1].state.previous_goal_eval if steps else "",
                        "memory": "",
                        "next_goal": "",
                        "action": collected_actions,
                        "thinking": "\n".join(step_texts),
                    },
                    "result": step_results or [{
                        "is_done": False,
                        "long_term_memory": "",
                        "extracted_content": "",
                        "include_extracted_content_only_once": False,
                        "include_in_memory": False,
                    }],
                    "metadata": {
                        "step_start_time": step_start_time,
                        "step_end_time": step_end_time,
                        "step_number": step_num,
                    },
                })

            if last_step_num >= max_steps:
                hit_max_steps = True

            try:
                await context.close()
            except Exception:
                logging.debug("[CLEANUP] context close failed")
            try:
                await browser.close()
            except Exception:
                logging.debug("[CLEANUP] browser close failed")

        latency = max(0.001, time.time() - start_ts)
        # If no tokens were collected during steps (edge cases), attempt a single usage read
        try:
            if not tokens and 'response' in locals() and hasattr(response, 'usage'):
                tokens.append(TokenInfo(
                    prompt_tokens=getattr(response.usage, 'input_tokens', 0),
                    completion_tokens=getattr(response.usage, 'output_tokens', 0),
                    total_tokens=(getattr(response.usage, 'input_tokens', 0) + getattr(response.usage, 'output_tokens', 0))
                ))
        except Exception:
            pass
        if hit_max_steps:
            success = False
            error_msg = "Maximum steps reached"
        final_text = last_text if success else ("ERROR: " + error_msg if error_msg else "")
        # Fill result per neurosim Evaluation contract
        self.result.jobId = self.request.jobid
        self.result.success = success
        self.result.latency = latency
        self.result.tokens = [t.model_dump() for t in tokens]
        self.result.task = {"taskId": str(self.request.taskid), "task": self.request.task, "model": self.config.model}
        # Ensure results schema ordering and fields parity:
        # - steps may be non-empty for internal tracing, but OpenAI result artifact only
        #   requires top-level fields and a terminal results/error. Keep steps for now,
        #   but do not append any extra diagnostics fields to the final artifact.
        self.result.steps = [s.model_dump() for s in steps]
        self.result.results = final_text
        if not success:
            self.result.error = {"message": error_msg}
        # Write compressed result.zst (parity with OpenAI/Notte local outputs)
        try:
            payload = self.result.model_dump() if hasattr(self.result, "model_dump") else dict(self.result.__dict__)
            # Ensure no extra diagnostics fields leak into final artifact
            if isinstance(payload, dict) and "steps_diagnostics" in payload:
                payload.pop("steps_diagnostics", None)
            out_path = os.path.join(self.config.save_path, "result.zst")
            cctx = zstd.ZstdCompressor()
            data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            with open(out_path, "wb") as f:
                f.write(cctx.compress(data))
        except Exception:
            # Best-effort; do not fail run on artifact write
            logging.exception("[RESULT] Failed to write result.zst")
        
        # Optional: upload result and screenshots to GCS, matching OpenAI behavior
        try:
            bucket_name = os.getenv("BUCKET_NAME") or os.getenv("GCS_BUCKET_NAME") or getattr(self.request, "bucket_name", "")
            if bucket_name:
                try:
                    from google.cloud import storage  # type: ignore
                except Exception:
                    storage = None  # type: ignore
                if storage is not None:
                    client = storage.Client()
                    bucket = client.bucket(bucket_name)
                    prefix = f"{self.request.userid}/{self.request.jobid}/{self.request.episode}/{self.request.taskid}"
                    # Upload result.zst
                    result_file = Path(self.config.save_path) / "result.zst"
                    if result_file.exists():
                        blob = bucket.blob(f"{prefix}/result.zst")
                        blob.upload_from_filename(str(result_file))
                        logging.info("[GCS] uploaded %s to gs://%s/%s", result_file, bucket_name, f"{prefix}/result.zst")
                    # Upload screenshots
                    for png in sorted(Path(self.config.save_path).glob("screenshot_*.png")):
                        blob = bucket.blob(f"{prefix}/{png.name}")
                        blob.upload_from_filename(str(png))
                        logging.info("[GCS] uploaded %s to gs://%s/%s", png, bucket_name, f"{prefix}/{png.name}")
                else:
                    logging.warning("[GCS] google-cloud-storage not installed; skipping uploads")
            else:
                logging.info("[GCS] no BUCKET_NAME provided; skipping uploads")
        except Exception as e:
            logging.warning("[GCS] upload failed: %s", e)
        return self.result

    def compute_steps(self) -> None:
        # Steps are already normalized and saved during run()
        return

    def compute_tokens(self) -> None:
        # Tokens were collected during run()
        return


if __name__ == "__main__":
    RunEvaluation = AnthropicEvaluation.from_cli()
    try:
        asyncio.run(asyncio.wait_for(RunEvaluation.execute(), timeout=1800))
    except asyncio.TimeoutError:
        import sys
        sys.exit(124)

