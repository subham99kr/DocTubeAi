from pymongo import ReplaceOne
import logging
from uuid import uuid4
from global_modules.embeddings import embeddings
from global_modules.mongo_collections import collection

from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

def insert_chunks(chunks):
    if not chunks:
        print("No chunks to insert")
        return

    # -------------------- BATCH EMBEDDING --------------------
    texts = [c.page_content for c in chunks]
    vectors = embeddings.embed_documents(texts) 

    ops =[]
    for chunk, vector_of_text in zip(chunks, vectors):     
        text = chunk.page_content
        
        # Access the metadata 
        metadata = chunk.metadata 
        session_id = metadata.get("session_id")
        source = metadata.get("source")

        vector_of_text = vector_of_text.tolist() if hasattr(vector_of_text, "tolist") else vector_of_text
        unique_id = str(uuid4())

        doc = {
            "_id": unique_id,
            "session_id": session_id,
            "source": source,
            "text": text,
            "embedding": vector_of_text
        }
        ops.append(ReplaceOne({"_id": unique_id}, doc, upsert=True))

    if ops:
        try:
            collection.bulk_write(ops, ordered=False)
            logger.info(f"🟢 Bulk write completed for session : {session_id}")
        except Exception as e:
            logger.exception("🔴 Bulk write failed")
    print(f"Inserted {len(chunks)} chunks into MongoDB.")