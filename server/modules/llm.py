import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

CHAT_MODELS = [
    m.strip() for m in os.getenv("CHAT_MODELS", "").split(",") if m.strip()
]

TOOL_MODELS = [
    m.strip() for m in os.getenv("TOOL_MODELS", "").split(",") if m.strip()
]

def _get_llm(models, temperature: float):
    """
    Returns the first available model.
    Falls back automatically on failure.
    """
    last_error = None

    for model in models:
        try:
            return ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model_name=model,
                temperature=temperature,
                
            )
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"No LLM models available. Last error: {last_error}"
    )


def get_chat_model():
    """
    Chat-only LLM.
    - Used for explanations, debugging, reasoning
    - NEVER binds tools
    """
    return _get_llm(
        models=CHAT_MODELS,
        temperature=0.3,
    )


def get_tool_model():
    """
    Tool-capable LLM.
    - Tools are bound ONLY inside tool nodes
    """
    return _get_llm(
        models=TOOL_MODELS,
        temperature=0,
    )


def get_chatbot_prompt():
    """
    Prompt template for chat reasoning.
    This prompt NEVER assumes tool usage.
    """
    return ChatPromptTemplate.from_messages([
        (
            "system",
            """You are an ai assistant that can do multi-source verification. Your name is "DocTubeAi".

                FOR COMPLEX QUERY YOU CAN:
                1. Use web-scraped content to summarize the primary source.
                2. Cross-check claims using:
                - Internal database search results
                - Internet search results
                3. Explicitly state:
                - What is confirmed
                - What is outdated or inconsistent
                - What could not be verified
                4. If multiple sources agree, say so.
                5. If sources disagree, highlight the discrepancy.
                6. Do NOT provide a generic summary when verification was requested.
                7. In the end also provide the origins only if you had tool calls.
            """
        ),
        MessagesPlaceholder(variable_name="messages"),
    ])
