from langchain_groq import ChatGroq
# from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from dotenv import load_dotenv
import os

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MAIN_LLM_MODEL = os.environ.get("MAIN_LLM_MODEL")
SUMMARY_LLM_MODEL = os.environ.get("SUMMARY_LLM_MODEL")

get_llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name=MAIN_LLM_MODEL,
)

summary_llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name=SUMMARY_LLM_MODEL,
)

# 2. The Prompt Factory
def get_chatbot_prompt():
    """Returns the prompt template only."""
    return ChatPromptTemplate.from_messages([
        ("system", """You are a helpful RAG assistant.From the users query and past messages identify which tools to use like vector search, internet search and web scraper to get context.Answer the user's question using the provided context.If you are answering in Hindi or other language do not use JSON formatting. Provide a natural text response."
        
        GUIDELINES:
        1. Priority: Uploaded Documents > Internet Search.
        2. Previous conversation summary for context: {summary}
        3. Maintain a professional tone."""),
        
        MessagesPlaceholder(variable_name="messages"),
    ])

# 3. The Model Factory (This is what you pass to the Graph Builder)
def get_model():
    """Returns the raw LLM object so we can call .bind_tools() on it."""
    return get_llm
