
import logging
logger = logging.getLogger(__name__)

async def run_tavily_search(client, query: str, max_results: int = 3) -> str:
    """
    Fetches search results and formats them with metadata for better LLM grounding.
    """
    try:
        # 1. Execute search
        response = await client.search(
            query=query,
            search_depth="basic", # 'advanced' is better but costs 2 credits per 5 results
            max_results=max_results,
        )
        
        results = response.get("results", [])
        if not results:
            return "No relevant search results found."

        # 2. Format it with metadata
        # Adding Title and URL helps the LLM avoid 'hallucinating' source info
        formatted_results = []
        for i, res in enumerate(results, 1):
            title = res.get("title", "No Title")
            url = res.get("url", "No URL")
            content = res.get("content", "").strip()
            score = res.get("score", 0)

            # Optional: Filter out very low relevance results
            if score < 0.3: 
                continue

            entry = f"[{i}] Source: {title}\nURL: {url}\nContent: {content}\n"
            formatted_results.append(entry)

        # 3. Join and Truncate
        final_context = "\n---\n".join(formatted_results)
        return final_context[:7000] 

    except Exception as e:
        logger.error(f"❌ Tavily API logic failed: {str(e)}", exc_info=True)
        return "Error: Unable to fetch search results at this time."

# import logging

# logger = logging.getLogger(__name__)

# async def run_tavily_search(client, query: str, max_results: int = 3) -> str:
#     """Renamed to avoid collision with the tool name"""
#     try:
#         response = await client.search(
#             query=query,
#             search_depth="basic",
#             max_results=max_results,
#         )
#         results = response.get("results", [])
#         content_list = [r["content"] for r in results if r.get("content")]
#         return " ".join(content_list)[:6000]

#     except Exception as e:
#         # This will print the FULL stack trace to your terminal
#         logger.error(f"❌ Tavily API logic failed: {str(e)}", exc_info=True)
#         return ""