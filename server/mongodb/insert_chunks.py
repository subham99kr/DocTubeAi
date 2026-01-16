# from pymongo import ReplaceOne
# import logging
# from uuid import uuid4
# from global_modules.embeddings import embeddings
# from global_modules.mongo_collections import collection

# from dotenv import load_dotenv
# load_dotenv()
# logger = logging.getLogger(__name__)

# def insert_chunks(chunks):
#     if not chunks:
#         print("No chunks to insert")
#         return

#     # -------------------- BATCH EMBEDDING --------------------
#     texts = [c.page_content for c in chunks]
#     vectors = embeddings.embed_documents(texts) 

#     ops =[]
#     for chunk, vector_of_text in zip(chunks, vectors):     
#         text = chunk.page_content
        
#         # Access the metadata 
#         metadata = chunk.metadata 
#         session_id = metadata.get("session_id")
#         source = metadata.get("source")

#         vector_of_text = vector_of_text.tolist() if hasattr(vector_of_text, "tolist") else vector_of_text
#         unique_id = str(uuid4())

#         doc = {
#             "_id": unique_id,
#             "session_id": session_id,
#             "source": source,
#             "text": text,
#             "embedding": vector_of_text
#         }
#         ops.append(ReplaceOne({"_id": unique_id}, doc, upsert=True))

#     if ops:
#         try:
#             collection.bulk_write(ops, ordered=False)
#             logger.info(f"🟢 Bulk write completed for session : {session_id}")
#         except Exception as e:
#             logger.exception("🔴 Bulk write failed")
#     print(f"Inserted {len(chunks)} chunks into MongoDB.")

from pymongo import ReplaceOne
import logging
from uuid import uuid4
from global_modules.embeddings import embeddings
from global_modules.mongo_collections import collection

logger = logging.getLogger(__name__)

async def insert_chunks(chunks):
    if not chunks:
        return

    # 1. Prepend title to content for every chunk before embedding
    processed_texts = []
    for c in chunks:
        source_name = c.metadata.get("source", "Unknown Source")
        # Every chunk gets its source prepended so the Vector 'knows' the file name
        enhanced_text = f"SOURCE: {source_name}\n\n{c.page_content}"
        processed_texts.append(enhanced_text)

    # 2. Batch Embedding (Embedding models are usually sync, but run fast)
    vectors = embeddings.embed_documents(processed_texts) 

    ops = []
    for i, (chunk, vector_of_text) in enumerate(zip(chunks, vectors)):     
        metadata = chunk.metadata 
        
        doc = {
            "_id": str(uuid4()),
            "session_id": metadata.get("session_id"),
            "source": metadata.get("source"),
            "text": processed_texts[i], # Save text with the title
            "embedding": vector_of_text.tolist() if hasattr(vector_of_text, "tolist") else vector_of_text
        }
        ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))

    if ops:
        # 3. Async Bulk Write
        await collection.bulk_write(ops, ordered=False)
        logger.info("🟢 Bulk write completed successfully")