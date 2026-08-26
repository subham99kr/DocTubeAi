from pymongo import MongoClient
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import os
import traceback

# ============================================================
# CONFIG
# ============================================================

load_dotenv("server/.env", override=True)

MONGODB_URI = os.getenv("MONGODB_URI_STRING")

DATABASE = "rag_db"
COLLECTION = "documents"
INDEX_NAME = "vector_index"

SESSION_ID = "94f12674-972c-45d3-94f7-cbf7fd0289cc"

QUERY = "What is retrieval augmented generation?"

# ============================================================
# CONNECT
# ============================================================

print("\n[1] Connecting to MongoDB...")

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10000
)

db = client[DATABASE]
collection = db[COLLECTION]

try:
    client.admin.command("ping")
    print("✅ MongoDB connection OK")
except Exception as e:
    print("❌ MongoDB connection failed")
    print(e)
    exit()


# ============================================================
# CHECK DOCUMENTS
# ============================================================

print("\n[2] Checking documents...")

count = collection.count_documents({
    "session_id": SESSION_ID
})

print(f"Documents for session: {count}")

if count == 0:
    print("❌ No documents found for this session")
    exit()


# ============================================================
# CHECK ONE DOCUMENT
# ============================================================

print("\n[3] Inspecting document...")

doc = collection.find_one({
    "session_id": SESSION_ID
})

print("Document found:")
print("  _id:", doc.get("_id"))
print("  session_id:", doc.get("session_id"))
print("  source:", doc.get("source"))

embedding = doc.get("embedding")

print("  embedding exists:", embedding is not None)
print("  embedding type:", type(embedding).__name__)

if embedding:
    print("  embedding length:", len(embedding))
    print("  first 5 values:", embedding[:5])

print("  text length:", len(doc.get("text", "")))
print("  text preview:")
print(doc.get("text", "")[:300])


# ============================================================
# CREATE QUERY EMBEDDING
# ============================================================

print("\n[4] Creating query embedding...")

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

query_embedding = model.encode(
    QUERY,
    normalize_embeddings=True
).tolist()

print("✅ Query embedding created")
print("  dimension:", len(query_embedding))
print("  first 5 values:", query_embedding[:5])


# ============================================================
# VECTOR SEARCH WITHOUT SESSION FILTER
# ============================================================

print("\n[5] Vector search WITHOUT session filter...")

pipeline = [
    {
        "$vectorSearch": {
            "index": INDEX_NAME,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 50,
            "limit": 5
        }
    },
    {
        "$project": {
            "_id": 0,
            "session_id": 1,
            "source": 1,
            "text": 1,
            "score": {
                "$meta": "vectorSearchScore"
            }
        }
    }
]

try:

    results = list(
        collection.aggregate(pipeline)
    )

    print(f"Results: {len(results)}")

    for i, result in enumerate(results, 1):

        print("\n--- RESULT", i, "---")
        print("session_id:", result.get("session_id"))
        print("source:", result.get("source"))
        print("score:", result.get("score"))
        print("text:")
        print(result.get("text", "")[:500])

except Exception:

    print("❌ Vector search failed")

    traceback.print_exc()


# ============================================================
# VECTOR SEARCH WITH SESSION FILTER
# ============================================================

print("\n[6] Vector search WITH session filter...")

pipeline = [
    {
        "$vectorSearch": {
            "index": INDEX_NAME,
            "path": "embedding",
            "queryVector": query_embedding,
            "numCandidates": 50,
            "limit": 5,
            "filter": {
                "session_id": SESSION_ID
            }
        }
    },
    {
        "$project": {
            "_id": 0,
            "session_id": 1,
            "source": 1,
            "text": 1,
            "score": {
                "$meta": "vectorSearchScore"
            }
        }
    }
]

try:

    results = list(
        collection.aggregate(pipeline)
    )

    print(f"Results: {len(results)}")

    for i, result in enumerate(results, 1):

        print("\n--- RESULT", i, "---")
        print("session_id:", result.get("session_id"))
        print("source:", result.get("source"))
        print("score:", result.get("score"))
        print("text:")
        print(result.get("text", "")[:500])

except Exception:

    print("❌ Filtered vector search failed")

    traceback.print_exc()


print("\n================================================")
print("TEST COMPLETE")
print("================================================")