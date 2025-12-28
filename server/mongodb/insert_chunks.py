from pymongo import MongoClient, ReplaceOne
import os
import logging
from uuid import uuid4
from modules.embeddings import embeddings

from dotenv import load_dotenv
load_dotenv()

uri = os.environ.get("MONGODB_URI_STRING")
client = MongoClient(uri)
coll = client["rag_db"]["documents"]
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
logger = logging.getLogger(__name__)

def insert_chunks(chunks):
    if not chunks:
        print("No chunks to insert")
        return

    # -------------------- BATCH EMBEDDING --------------------
    # FIX: Document objects use the attribute .page_content for the text.
    texts = [c.page_content for c in chunks]
    vectors = embeddings.embed_documents(texts) 
    # -------------------------------------------------------------------------

    ops =[]
    for chunk, vector_of_text in zip(chunks, vectors): 
        # FIX: Access attributes using dot notation. 
        # .page_content for text, .metadata for the metadata dictionary.     
        text = chunk.page_content
        
        # Access the metadata dictionary using .metadata, then use dictionary .get()
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
            coll.bulk_write(ops, ordered=False) 
        except Exception as e:
            logger.exception("Bulk write failed")
    print(f"Inserted {len(chunks)} chunks into MongoDB.")