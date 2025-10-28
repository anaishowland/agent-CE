"""Browser Use Evaluation Module

This module implements a browser-based evaluation system that uses an AI agent to perform
automated web browsing tasks. It provides functionality for executing, monitoring, and
analyzing browser automation tasks with configurable parameters and error handling.

The module primarily consists of the BrowseruseEvaluation class which extends the base
Evaluation class to implement browser-specific evaluation logic.

Key Features:
    - Browser session management with configurable profiles
    - AI agent integration for automated web navigation
    - Screenshot capture and management
    - Token usage tracking
    - Comprehensive error handling for network and browser issues
    - Support for async execution with timeout controls

Classes:
    BrowseruseEvaluation: Main class that handles browser-based evaluation tasks

Dependencies:
    - browser_use: For browser automation and agent functionality
    - neurosim: For evaluation framework and result handling
    - logging: For logging evaluation progress and errors
    - asyncio: For asynchronous execution support
"""
import logging
import time
import os
import sys
import traceback
from typing import List, Union
from importlib.metadata import version, PackageNotFoundError

from browser_use import Agent, BrowserSession, BrowserProfile
from browser_use.browser.profile import BrowserChannel
from browser_use.agent.views import AgentHistoryList
from browser_use.llm import ChatOpenAI
from browser_use.llm import ChatGoogle
from browser_use.llm import ChatAnthropic

from neurosim.evaluation import Evaluation
from neurosim.utils.models import EvaluationRequest, AgentResult, AgentErrors

from BrowseruseEvaluation.llm import llm_config

logger = logging.getLogger(__name__)


class BrowseruseEvaluation(Evaluation):
    """BrowseruseEvaluation class for executing evaluation tasks using the Notte agent.

    This class extends the abstract `Evaluation` class and implements the
    necessary methods to perform evaluations using the Notte agent. It
    initializes the evaluation configuration, sets up the agent version and
    name, and defines the logic for running the evaluation task.

    Attributes:
        response (AgentHistoryList[Unknown] | None): The response from agent run.

    Methods:
        __init__(request: EvaluationRequest):
            Initializes the NotteEvaluation instance with the given request.

        get_llm() -> str:
            Retrieves the language model name to be used for evaluation.

        run() -> AgentResult:
            Executes the evaluation task using the Notte agent and returns the results.
    """
    browser_profile: BrowserProfile
    response: AgentHistoryList | None

    def __init__(self, request: EvaluationRequest):
        super().__init__(request)
        self.response = None
        self.agent_name = "Browser Use"
        try:
            self.agent_version = version("browser-use")
        except PackageNotFoundError:
            self.agent_version = "unknown"
        self.browser_profile = BrowserProfile(
            headless=False,
            keep_alive=False,
            wait_for_network_idle_page_load_time=2,
            channel=BrowserChannel.CHROME,
            viewport={'width': 1290, 'height': 1080}  # type: ignore
        )

    def get_llm(self) -> Union[ChatGoogle, ChatOpenAI, ChatAnthropic]:
        try:
            return llm_config(self.request.model,
                    float(self.request.advanced_settings.get(
                        "temperature", 0)),
                    int(self.request.advanced_settings.get('max_retries', 2)))
        except ValueError as e:
            logger.error(f"Error configuring LLM {self.request.model}: {e}")
            sys.exit(1)

    async def run(self) -> AgentResult:
        self.response = None
        system_prompt: str = """
            CAUTION: 
                1. If hit with captcha more than two times, end executing the particular tasks and go to next task.
            """
        try:
            session = BrowserSession(browser_profile=self.browser_profile)
            agent = Agent(
                browser_session=session,
                task=self.request.task,
                max_actions_per_step=int(
                    self.request.advanced_settings.get("max_actions_per_step", 10)),
                llm=self.config.model,
                task_id=self.request.taskid,
                max_failures=int(
                    self.request.advanced_settings.get('max_retries', 2)),
                use_vision=self.request.advanced_settings.get(
                    "use_vision", True),
                enable_memory=False,
                generate_gif=self.request.advanced_settings.get(
                    'generate_gif', False),
                override_system_message=system_prompt
            )
            self.response = await agent.run(
                max_steps=int(
                    self.request.advanced_settings.get('max_steps', 50))
            )
            total_duration = sum(
                item.metadata.duration_seconds
                for item in self.response.history
                if item.metadata is not None
            )
            self.result.latency = total_duration
            answer = self.response.final_result()
            if answer is not None:
                self.result.results = answer
                self.result.success = self.response.is_successful() or False
        except (TimeoutError, ConnectionError) as e:
            self.result.results = f"Network Error: {str(e)}"
            self.result.error = AgentErrors(
                name="Network Error",
                traceback=traceback.format_exc(),
                error=str(e)
            )
        except RuntimeError as e:
            self.result.results = f"Browser Error: {str(e)}"
            self.result.error = AgentErrors(
                name="Browser Error",
                traceback=traceback.format_exc(),
                error=str(e)
            )
        return self.result

    def compute_steps(self):
        if self.response:
            steps: List = [history.model_dump()
                           for history in self.response.history]
            self.result.steps = steps
            for index, entry in enumerate(steps):
                timestamp = int(time.time())
                source_path = entry["state"]["screenshot_path"]
                if source_path is not None:
                    destination_path = os.path.join(
                        self.config.save_path, f"screenshot_{timestamp}_{index+1}.png")
                    try:
                        with open(source_path, 'rb') as src_file:
                            self.save_screenshots(
                                src_file.read(), f"screenshot_{timestamp}_{index+1}.png")
                            with open(destination_path, 'wb') as dest_file:
                                dest_file.write(src_file.read())
                        self.result.steps[index]["screenshot"] = destination_path
                    except OSError as e:
                        logging.error(
                            "[ERROR] Error copying file from %s to %s: %s",
                            source_path, destination_path, e)

    def compute_tokens(self):
        if self.response:
            if self.response.usage:
                self.result.tokens = [
                    {
                        "prompt_tokens": self.response.usage.total_prompt_tokens,
                        "completion_tokens": self.response.usage.total_completion_tokens,
                        "total_tokens": self.response.usage.total_tokens
                    }
                ]


if __name__ == "__main__":
    import asyncio
    import sys
    RunEvaluation = BrowseruseEvaluation.from_cli()
    try:
        asyncio.run(asyncio.wait_for(RunEvaluation.execute(), timeout=5400))
        logger.info(
            "✅ Evaluation completed successfully (jobId=%s, taskId=%s)",
            RunEvaluation.request.jobid,
            RunEvaluation.request.taskid,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Evaluation timed out after %s seconds (jobId=%s, taskId=%s)",
            5400,
            RunEvaluation.request.jobid,
            RunEvaluation.request.taskid,
        )
        sys.exit(124)
