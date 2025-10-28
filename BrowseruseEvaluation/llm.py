"""
This module provides a configuration interface for various Language Learning Models (LLMs).

It supports multiple LLM providers including Google's Gemini models, OpenAI's GPT models,
and Anthropic's Claude models. The module handles the initialization and configuration
of these models with appropriate parameters and API keys.

Models Supported:
    - Google Gemini models (2.0 and 2.5 variants)
    - OpenAI GPT models (various versions)
    - Anthropic Claude models (opus and sonnet variants)

Environment Variables Required:
    - GOOGLE_API_KEY: For Google Gemini models
    - OPENAI_API_KEY: For OpenAI GPT models
    - ANTHROPIC_API_KEY: For Anthropic Claude models

Dependencies:
    - browser_use.llm.ChatOpenAI
    - browser_use.llm.ChatGoogle
    - browser_use.llm.ChatAnthropic
"""

import os
from typing import Union
from browser_use.llm import ChatOpenAI
from browser_use.llm import ChatGoogle
from browser_use.llm import ChatAnthropic


def llm_config(
        model: str,
        temperature: float = 0,
        max_retries: int = 2) -> Union[ChatGoogle, ChatOpenAI, ChatAnthropic]:
    """
    Configure and return a Language Model instance based on the specified model name.
    This function initializes different LLM instances (Google's Gemini,
    OpenAI's GPT, or Anthropic's Claude) with specified configuration parameters.
    Args:
        model (str): The name/identifier of the LLM model to use. Supported models include:
            - Gemini models: 'gemini-2.5-flash-preview-05-20', 'gemini-2.5-pro-preview-06-05',
                'gemini-2.0-flash-lite', 'gemini-2.5-flash-lite'
            - GPT models: 'gpt-4o', 'gpt-o1', 'gpt-o3', 'gpt-4.1', 'gpt-o3-pro', 'gpt-o4-mini'
            - Claude models: 'claude-opus-4-20250514', 'claude-sonnet-4-20250514',
                'claude-3-7-sonnet-latest' temperature (float, optional):
                Controls randomness in the model's output. Defaults to 0.
        max_retries (int, optional): Maximum number of retry attempts for failed API calls.
            Defaults to 2.
    Returns:
        Union[ChatGoogle, ChatOpenAI, ChatAnthropic]: Configured LLM instance
        based on the specified model. Defaults to Gemini-2.5-flash if an
        unsupported model is specified.
    Note:
        Requires appropriate API keys to be set in environment variables:
        - GOOGLE_API_KEY for Gemini models
        - OPENAI_API_KEY for GPT models
        - ANTHROPIC_API_KEY for Claude models
    """

    match str(model):
        case 'gemini-2.5-flash-preview-05-20':
            llm = ChatGoogle(
                model="gemini-2.5-flash",
                temperature=temperature,
                vertexai=True,
                project=os.getenv("GCP_PROJECT_ID", "your-gcp-project-id"),
                location="us-central1",
                # other params...
            )
        case 'gemini-2.5-pro-preview-06-05':
            llm = ChatGoogle(
                model="gemini-2.5-pro",
                temperature=temperature,
                vertexai=True,
                project=os.getenv("GCP_PROJECT_ID", "your-gcp-project-id"),
                location="us-central1",
            )
        case 'gemini-2.0-flash-lite':
            llm = ChatGoogle(
                model="gemini-2.0-flash-lite",
                temperature=temperature,
                vertexai=True,
                project=os.getenv("GCP_PROJECT_ID", "your-gcp-project-id"),
                location="us-central1",
            )
        case 'gemini-2.5-flash-lite':
            llm = ChatGoogle(
                model="gemini-2.5-flash-lite-preview-06-17",
                temperature=temperature,
                vertexai=True,
                project=os.getenv("GCP_PROJECT_ID", "your-gcp-project-id"),
                location="us-central1",
            )
        case 'gpt-4o':
            llm = ChatOpenAI(model='gpt-4o', max_retries=max_retries,
                             temperature=temperature, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-o1':
            llm = ChatOpenAI(model='o1', temperature=temperature,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-o3':
            llm = ChatOpenAI(model="o3", temperature=temperature,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-4.1':
            llm = ChatOpenAI(model="gpt-4.1", temperature=temperature,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-o3-pro':
            llm = ChatOpenAI(model='o3-pro', temperature=temperature,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-o4-mini':
            llm = ChatOpenAI(model='o4-mini', temperature=temperature,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-5':
            llm = ChatOpenAI(model='gpt-5', temperature=1,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-5-mini':
            llm = ChatOpenAI(model='gpt-5-mini', temperature=1,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'gpt-5-nano':
            llm = ChatOpenAI(model='gpt-5-nano', temperature=1,
                             max_retries=max_retries, api_key=os.getenv("OPENAI_API_KEY", ''))
        case 'claude-opus-4.1':
            llm = ChatAnthropic(
                model="claude-opus-4-1-20250805",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                timeout=None,
                temperature=temperature,
                max_retries=max_retries
            )
        case 'claude-opus-4-20250514':
            llm = ChatAnthropic(
                model="claude-opus-4-20250514",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                timeout=None,
                temperature=temperature,
                max_retries=max_retries
            )
        case 'claude-sonnet-4-20250514':
            llm = ChatAnthropic(
                model="claude-sonnet-4-20250514",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                timeout=None,
                temperature=temperature,
                max_retries=max_retries
            )
        case 'claude-3-7-sonnet-latest':
            llm = ChatAnthropic(
                model="claude-3-7-sonnet-latest",
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                timeout=None,
                temperature=temperature,
                max_retries=max_retries
            )
        case _:
            raise ValueError(f"Model {model} not supported")
    return llm
