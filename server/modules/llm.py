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
        ("system", """You are a helpful RAG assistant.From the users query and past messages identify which tools to use like vector search, internet search and web scraper to get context.
        
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

# def get_llm_runnable():
    
#     prompt = ChatPromptTemplate.from_messages([
#     ("system", """You are a helpful and friendly assistant. Use the provided context to answer the user's query.
    
#     GUIDELINES:
#     1. If the answer is not in the context, use the summary and chat history.
#     2. If you still cannot find the answer, politely state that you don't know rather than hallucinating.
#     3. Always prioritize information from 'Uploaded docs | Youtube link(transcript in context)' then . If there is a conflict and unless specific prioritization from user.
#     4. Maintain a conversational and professional tone.
#     5. If you use information from 'Supplementary Context', briefly mention which source it came from (e.g., "According to the uploaded documents..." or "Based on a web search...")."""),
    
    
#     ("human", """### PREVIOUS CONVERSATION SUMMARY
#     {summary}

#     ### RECENT CHAT HISTORY - Past 2 messages 
#     {history}

#     ### SUPPLEMENTARY CONTEXT
#     - Document Retrieval: {vector_context}
#     - Direct Web Scrape: {scraped_text}
#     - General Internet Search: {web_results}

#     ### USER QUERY
#     {query}

#     Assistant, please generate your response based on the above information:""")
#     ])

#     chain = (
#     {
#         "summary": lambda x: x.get("summary", "No summary"),
#         "history": lambda x: "\n".join(
#                 [f"{msg.type.capitalize()}: {msg.content}" for msg in x["messages"][-3:-1]]
#             ) if x.get("messages") and len(x["messages"]) > 1 else "No recent history",

#         "vector_context": lambda x: x.get("vector_context", ""),
#         "scraped_text": lambda x: x.get("scraped_text", ""),
#         "web_results": lambda x: x.get("web_results", ""),
#         "query": lambda x: x.get("query", "")
#     }
#     | prompt 
#     | get_llm 
#     | StrOutputParser()
#     )
#     return chain


