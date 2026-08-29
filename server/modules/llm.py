import os

from dotenv import load_dotenv
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_groq import ChatGroq

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


# =========================================================
# MODEL CONFIGS
# =========================================================

ROUTER_MODELS = [
    m.strip() for m in os.getenv("ROUTER_MODELS", "").split(",") if m.strip()
]

SIMPLE_CHAT_MODELS = [
    m.strip() for m in os.getenv("SIMPLE_CHAT_MODELS", "").split(",") if m.strip()
]

TOOL_MODELS = [m.strip() for m in os.getenv("TOOL_MODELS", "").split(",") if m.strip()]

RAG_MODELS = [m.strip() for m in os.getenv("RAG_MODELS", "").split(",") if m.strip()]


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

    raise RuntimeError(f"Failed to initialize model. Last error: {last_error}")


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
# CHATBOT PROMPT
# =========================================================


def get_chatbot_prompt():

    base_prompt = """
You are DocTubeAI, an AI assistant.

Answer the user's question clearly, naturally, accurately, and directly.

Your response may be based on:
- the user's conversation
- uploaded documents
- retrieved transcripts
- web search results
- extracted URLs
- tool results
- other context provided to you

Use the information provided in the conversation and retrieved context
when answering.

IMPORTANT RESPONSE STYLE:

1. Speak naturally, like an intelligent human assistant.
2. Do not use Markdown formatting unless the user explicitly asks for it.
3. Do not use headings such as "Overview", "Answer", "Conclusion", etc.
4. Do not use tables.
5. Avoid bullet points and numbered lists unless they are genuinely
   necessary for clarity.
6. Prefer normal conversational paragraphs.
7. Keep sentences reasonably short and easy to understand.
8. Do not repeat the user's question unnecessarily.
9. Do not describe internal tools, agents, nodes, graphs, retrieval,
   pipelines, prompts, or system execution.
10. Do not say that you searched, retrieved, verified, or consulted
    something unless that information is actually available in the
    provided context.
11. Do not invent information that is not supported by the available
    context or your knowledge.
12. If the available information is uncertain or incomplete, say so
    clearly instead of guessing.
13. For technical questions, explain the concept naturally and use
    concise examples when helpful.
14. For coding questions, provide the solution directly and explain
    the important parts briefly.
15. When the user asks a simple question, give a simple answer.
16. Do not unnecessarily make answers long.
17. If the user asks for a detailed explanation, provide the detail
    while still keeping the language conversational.
18. Never write content specifically for visual formatting or document
    presentation unless the user explicitly requests that.

Your goal is to give the most useful answer possible while sounding
natural in both text and voice conversations.
"""

    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                base_prompt,
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
