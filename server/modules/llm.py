import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


# =========================================================
# MODEL CONFIGS
# =========================================================

ROUTER_MODELS = [
    m.strip()
    for m in os.getenv("ROUTER_MODELS", "").split(",")
    if m.strip()
]

SIMPLE_CHAT_MODELS = [
    m.strip()
    for m in os.getenv("SIMPLE_CHAT_MODELS", "").split(",")
    if m.strip()
]

TOOL_MODELS = [
    m.strip()
    for m in os.getenv("TOOL_MODELS", "").split(",")
    if m.strip()
]

RAG_MODELS = [
    m.strip()
    for m in os.getenv("RAG_MODELS", "").split(",")
    if m.strip()
]


# =========================================================
# BASE FACTORY
# =========================================================

def _build_llm(
    models,
    temperature: float,
):
    """
    Creates LLM instance from configured models.

    NOTE:
    This only validates model construction.
    Runtime failures still happen during:
    - invoke()
    - ainvoke()
    """

    if not models:
        raise RuntimeError("No models configured.")

    last_error = None

    for model in models:

        try:

            return ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model=model,
                temperature=temperature,
            )

        except Exception as e:

            last_error = e
            continue

    raise RuntimeError(
        f"Failed to initialize model. Last error: {last_error}"
    )


# =========================================================
# ROUTER MODEL
# =========================================================

def get_router_model():
    """
    Router classifier model.

    Responsibilities:
    - decide simple chat vs tools workflow
    - lightweight classification only

    SHOULD BE:
    - very fast
    - cheap
    """

    return _build_llm(
        models=ROUTER_MODELS,
        temperature=0,
    )


# =========================================================
# SIMPLE CHAT MODEL
# =========================================================

def get_simple_chat_model():
    """
    Direct response model.

    Used for:
    - greetings
    - coding questions
    - explanations
    - casual chat
    - unsupported requests
    - lightweight reasoning

    DOES NOT use retrieval.
    """

    return _build_llm(
        models=SIMPLE_CHAT_MODELS,
        temperature=0.3,
    )


# =========================================================
# TOOL PLANNER MODEL
# =========================================================

def get_tool_model():
    """
    Tool orchestration model.

    Responsibilities:
    - choose tools
    - emit tool calls
    - structured planning

    SHOULD BE:
    - deterministic
    - reliable with tools
    """

    return _build_llm(
        models=TOOL_MODELS,
        temperature=0,
    )


# =========================================================
# RAG SYNTHESIS MODEL
# =========================================================

def get_rag_model():
    """
    Final RAG synthesis model.

    Responsibilities:
    - combine retrieved evidence
    - compare sources
    - synthesize grounded answers
    - resolve contradictions

    This is the strongest reasoning model.
    """

    return _build_llm(
        models=RAG_MODELS,
        temperature=0.3,
    )


# =========================================================
# RAG PROMPT
# =========================================================

def get_chatbot_prompt():

    return ChatPromptTemplate.from_messages([
        (
            "system",
            """
            You are DocTubeAI, an AI assistant capable of multi-source reasoning and verification.

            Your responsibilities:
            1. Answer clearly and directly.
            2. Use retrieved evidence when available.
            3. Cross-check information across:
            - uploaded documents
            - transcript retrieval
            - internet search
            - URL extraction
            4. Clearly distinguish:
            - confirmed information
            - conflicting information
            - missing or unverifiable information
            5. If multiple sources agree, mention that.
            6. If sources disagree, explain the discrepancy.
            7. Avoid hallucinating unsupported claims.
            8. Do NOT pretend retrieval occurred if no tools were used.
            9. Keep responses concise unless detailed explanation is requested.
            """
        ),

        MessagesPlaceholder(variable_name="messages"),
    ])