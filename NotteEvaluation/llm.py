"""
    Convert llm request to agent understandable LLM id.
"""


def llm_config(model: str) -> str:
    """
    Retrieve the configuration for a specified language model.

    This function takes the name of a model as input and returns the
    corresponding configuration string. The configuration string is
    used to identify and access the appropriate language model for
    evaluation tasks.

    Args:
        model (str): The name of the model for which the configuration
                     is to be retrieved.

    Returns:
        str: The configuration string corresponding to the specified
             model name.
    """
    match str(model):
        case 'gemini-2.5-flash-preview-05-20':
            llm = "vertex_ai/gemini-2.5-flash"
        case 'gemini-2.0-flash':
            llm = "vertex_ai/gemini-2.0-flash"
        case 'gemini-2.0-flash-lite':
            llm = "vertex_ai/gemini-2.0-flash-lite"
        case 'gemini-2.5-flash-lite':
            llm = "vertex_ai/gemini-2.5-flash-lite-preview-06-17"
        case 'gemini-2.5-pro-preview-06-05':
            llm = "vertex_ai/gemini-2.5-pro"
        case 'gpt-4o':
            llm = "openai/gpt-4o"
        case 'gpt-4.1':
            llm = "openai/gpt-4.1"
        case 'gpt-o1':
            llm = "openai/o1"
        case 'gpt-o3':
            llm = "openai/o3"
        case 'gpt-o3-mini':
            llm = "openai/o3-mini"
        case 'gpt-o4-mini':
            llm = "openai/o4-mini"
        case 'gpt-5':
            llm = "openai/gpt-5"
        case 'gpt-5-mini':
            llm = "openai/gpt-5-mini"
        case 'gpt-5-nano':
            llm = "openai/gpt-5-pro"
        case _:
            raise ValueError(f"Model {model} not supported")
    return llm
