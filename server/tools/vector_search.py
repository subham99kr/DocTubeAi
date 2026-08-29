import logging

logger = logging.getLogger(__name__)
from global_modules.embeddings import embeddings as embeddings_model
from global_modules.mongo_collections import collection

# async def run_vector_search(query: str, session_id: str) -> str:
#     """
#     Search the vector database and return formatted context chunks.
#     """
#     try:
#         # 1. Generate Embedding
#         query_vector = await embeddings_model.aembed_query(query)
#         min_score = 0.4
#         num_chunks= 6

#         pipeline = [
#             {
#                 "$vectorSearch": {
#                     "index": "embedding_index",
#                     "queryVector": query_vector,
#                     "path": "embedding",
#                     "numCandidates": 400,
#                     "limit": num_chunks, 
#                     "filter": {"session_id": session_id},
#                 }
#             },
#             {
#                 "$project": {
#                     "_id": 0, 
#                     "text": 1, 
#                     "source": 1, # Useful if you store filenames/URLs
#                     "score": {"$meta": "vectorSearchScore"}
#                 }
#             },
#             {"$match": {"score": {"$gte": min_score}}}
#         ]
        
#         # 2. Execution (Motor for MongoDB uses 'async for' or 'to_list')
#         cursor = collection.aggregate(pipeline)
#         results = await cursor.to_list(length=num_chunks)

#         # if not results:
#         #     logger.info(f"No vector results for session {session_id} above score {min_score}")
#         #     return "No relevant information found in the uploaded documents."
#         # else:
#         #     logger.info(f"query: {query}")
#         #     logger.info(f"vector result: {results}")

#         # 3. Formatting for the LLM
#         # Using [Chunk X] helps the LLM distinguish between separate parts of a PDF/Video
#         formatted_chunks = []
#         for i, doc in enumerate(results, 1):
#             text = doc.get("text", "").strip()
#             source = doc.get("source", "Internal Doc")
#             score = round(doc.get("score", 0), 3)
            
#             chunk = f"--- Document Chunk {i} (Relevance: {score}) ---\nSource: {source}\nContent: {text}"
#             formatted_chunks.append(chunk)

#         return "\n\n".join(formatted_chunks)

#     except Exception as e:
#         logger.error(f"❌ Vector search failed: {str(e)}", exc_info=True)
#         return "Error searching internal documents."

async def run_vector_search(
    query: str,
    session_id: str
) -> str:

    try:

        logger.info(
            f"🔎 Vector query: {query}"
        )

        logger.info(
            f"🔐 Vector session_id: {session_id}"
        )

        # ============================================
        # EMBEDDING
        # ============================================

        query_vector = await embeddings_model.aembed_query(
            query
        )

        logger.info(
            f"🧠 Query embedding dimension: "
            f"{len(query_vector)}"
        )

        # ============================================
        # SEARCH
        # ============================================

        min_score = 0.4
        num_chunks = 6

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "queryVector": query_vector,
                    "path": "embedding",
                    "numCandidates": 400,
                    "limit": num_chunks,
                    "filter": {
                        "session_id": session_id
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "text": 1,
                    "source": 1,
                    "session_id": 1,
                    "score": {
                        "$meta": "vectorSearchScore"
                    },
                }
            },
        ]

        cursor = collection.aggregate(
            pipeline
        )

        results = await cursor.to_list(
            length=num_chunks
        )

        # ============================================
        # DEBUG
        # ============================================

        logger.info(
            f"📊 Vector results returned: "
            f"{len(results)}"
        )

        for i, doc in enumerate(
            results,
            1,
        ):

            logger.info(
                f"""
VECTOR RESULT {i}
session_id: {doc.get("session_id")}
source: {doc.get("source")}
score: {doc.get("score")}
text_length: {len(doc.get("text", ""))}
"""
            )

        # ============================================
        # SCORE FILTER
        # ============================================

        results = [
            doc
            for doc in results
            if doc.get("score", 0) >= min_score
        ]

        logger.info(
            f"📊 Results after score filter: "
            f"{len(results)}"
        )

        # ============================================
        # FORMAT
        # ============================================

        formatted_chunks = []

        for i, doc in enumerate(
            results,
            1,
        ):

            text = doc.get(
                "text",
                "",
            ).strip()

            source = doc.get(
                "source",
                "Internal Doc",
            )

            score = round(
                doc.get("score", 0),
                3,
            )

            formatted_chunks.append(
                f"""
--- Document Chunk {i} ---
Relevance: {score}
Source: {source}
Content: {text}
"""
            )

        return "\n\n".join(
            formatted_chunks
        )

    except Exception as e:

        logger.error(
            f"❌ Vector search failed: "
            f"{str(e)}",
            exc_info=True,
        )

        return ""