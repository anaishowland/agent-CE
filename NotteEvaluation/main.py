"""
This module serves as the entry point for executing evaluation tasks using the Notte agent.

The main functionality provided by this module includes setting up the environment,
configuring the Notte agent, and executing evaluation tasks. It leverages the
`NotteEvaluation` class, which extends the abstract `Evaluation` class, to perform
the necessary operations for task execution.

Key components:
- Environment setup for Notte configuration.
- Initialization and execution of the `NotteEvaluation` class.
- Handling of potential errors during task execution.

Usage:
    This module is intended to be run as a script to perform evaluation tasks.
    Ensure that the necessary environment variables and configurations are set
    before execution.

Dependencies:
    - Notte SDK and related modules for agent and browser management.
    - Neurosim utilities for evaluation and result handling.

Note:
    The module assumes that the Notte configuration file is located at
    './NotteEvaluation/notte_config.toml'.
"""

import time
import os
import traceback
import logging

import notte
from notte_browser.errors import BrowserExpiredError
from notte_core.errors.base import NotteBaseError
from notte_agent.common.types import AgentResponse

from neurosim.evaluation import Evaluation
from neurosim.utils.models import AgentErrors, AgentResult, EvaluationRequest
from NotteEvaluation.llm import llm_config
from notte_core.common.config import config
from loguru import logger

logger.info(
    f"[notte config] nb_retries_structured_output: {config.nb_retries_structured_output} and general nb_retries: {config.nb_retries}")

logger = logging.getLogger(__name__)


class NotteEvaluation(Evaluation):
    """NotteEvaluation class for executing evaluation tasks using the Notte agent.

    This class extends the abstract `Evaluation` class and implements the
    necessary methods to perform evaluations using the Notte agent. It
    initializes the evaluation configuration, sets up the agent version and
    name, and defines the logic for running the evaluation task.

    Attributes:
        response (AgentResponse | None): The response from agent run.

    Methods:
        __init__(request: EvaluationRequest):
            Initializes the NotteEvaluation instance with the given request.

        get_llm() -> str:
            Retrieves the language model name to be used for evaluation.

        run() -> AgentResult:
            Executes the evaluation task using the Notte agent and returns the results.
    """
    response: AgentResponse | None

    def __init__(self, request: EvaluationRequest):
        # Ensure config exists before base init uses it
        super().__init__(request)
        self.response = None
        self.agent_name = "Notte"
        self.agent_version = str(notte.__version__)

    def get_llm(self) -> str:
        """
        Retrieves the language model name to be used for evaluation.

        This method returns the name of the language model (LLM) that
        is specified in the evaluation request. The LLM is used by the
        Notte agent to perform the evaluation tasks.

        Returns:
            str: The name of the language model to be used for evaluation.
        """
        return llm_config(self.request.model)

    async def run(self) -> AgentResult:
        self.response = None
        async with notte.Session(
                headless=False,
                solve_captchas=False,
                timeout_minutes=1,
                browser_type='chrome',
                viewport_height=1280,
                viewport_width=1080) as session:
            try:
                agi = notte.Agent(
                    session=session,
                    reasoning_model=self.config.model,
                    max_steps=self.request.advanced_settings.get(
                        'max_steps', 50),
                    use_vision=self.request.advanced_settings.get(
                        'use_vision', True),
                )
                self.response = await agi.arun(task=self.request.task)
            except BrowserExpiredError as e:
                self.log.exception(
                    "[BrowserExpiredError] %s [Task Error] %s", e, self.request.task)
                # Restart session and retry
                agi = notte.Agent(
                    session=session,
                    reasoning_model=self.config.model,
                    max_steps=self.request.advanced_settings.get(
                        'max_steps', 50),
                    use_vision=self.request.advanced_settings.get(
                        'use_vision', True),
                )
                self.response = await agi.arun(task=self.request.task)
            except NotteBaseError as e:
                self.log.exception(
                    "[NotteBaseError] %s [Task Error] %s", e.dev_message, self.request.taskid)
                self.result.results = e.dev_message
                self.result.error = AgentErrors(
                    name="NotteBaseError", traceback=traceback.format_exc(), error=str(e.args))
                self.response = None
            finally:
                if self.response:
                    self.result.success = self.response.success
                    self.result.latency = self.response.duration_in_s
                    self.result.results = self.response.answer
        return self.result

    def compute_steps(self):
        if self.response:
            for _, step in enumerate(self.response.steps):
                step_dict = step.model_dump()
                if hasattr(self.result.steps, 'append'):
                    self.result.steps.append(step_dict)
                else:
                    self.log.error(
                        "self.result.steps does not have an 'append' method")
            for index, screenshot in enumerate(self.response.screenshots()):
                timestamp = int(time.time())
                screenshot_path = os.path.join(
                    self.config.save_path, f"screenshot_{timestamp}_{index+1}.png")
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot.bytes())
                self.result.steps[index]["screenshot"] = screenshot_path
                self.save_screenshots(screenshot.bytes(),
                                      f"screenshot_{timestamp}_{index+1}.png")

    def compute_tokens(self):
        if self.response:
            if self.response.llm_usage is not None:
                for step in self.response.llm_usage.steps:
                    if hasattr(self.result.steps, 'append'):
                        self.result.tokens.append(step.usage.model_dump())


if __name__ == "__main__":
    import asyncio
    import sys
    RunEvaluation = NotteEvaluation.from_cli()
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
