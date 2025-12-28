# run_vector_search_with_limit.py
import traceback
from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()

URI = os.environ.get("MONGODB_URI_STRING")
if not URI:
    print("ERROR: MONGODB_URI_STRING env var not set.")
    raise SystemExit(1)

try:
    client = MongoClient(URI)
    client.admin.command("ping")
    print("Ping OK")
except Exception as e:
    print("Ping failed:", type(e).__name__, e)
    traceback.print_exc()
    raise SystemExit(1)

db = client["rag_db"]
coll = db["documents"]

# index name from Atlas - use exact name
INDEX_NAME = "embedding_index"

total_docs = coll.count_documents({})
print("Total docs:", total_docs)

# Choose numCandidates and limit:
# - For very small collections we'll use exact behavior (numCandidates = total_docs)
# - Otherwise choose defaults you can tune.
if total_docs <= 200:
    numCandidates = max(total_docs, 1)
    limit = numCandidates
else:
    numCandidates = 400  # adjust upward for larger datasets
    limit = max(100, numCandidates // 2)

print("Using numCandidates:", numCandidates, "limit:", limit)

# helper to run pipeline and print results or exception
def run_pipeline(pipeline, desc):
    print(f"\n--- {desc} ---")
    try:
        res = list(coll.aggregate(pipeline))
        print("Result count:", len(res))
        for r in res[:10]:
            print(r)
    except Exception as e:
        print("AGGREGATION FAILED:", type(e).__name__, e)
        traceback.print_exc()

# fetch document
_id = "testsession::test.pdf::0"
doc = coll.find_one({"_id": _id})
print("Found doc:", bool(doc))
if doc and isinstance(doc.get("embedding"), list):
    print("embedding len:", len(doc['embedding']))

# vector + session filter
q0 = [0.5] * 384
pipe0 = [
    {"$vectorSearch": {
        "index": INDEX_NAME,
        "queryVector": q0,
        "path": "embedding",
        "k": 5,
        "numCandidates": numCandidates,
        "limit": limit
    }},
    {"$match": {"session_id": "not_that_session"}},
    {"$project": {"_id":1, "text":1, "source":1, "session_id":1}}
]
run_pipeline(pipe0, "vector with session filter (should return 0)")

# doc-vector (should return the doc)
if doc and isinstance(doc.get("embedding"), list):
    q_doc = doc["embedding"]
    pipe1 = [
        {"$vectorSearch": {
            "index": INDEX_NAME,
            "queryVector": q_doc,
            "path": "embedding",
            "k": 5,
            "numCandidates": numCandidates,
            "limit": limit
        }},
        {"$project": {"_id":1, "text":1, "source":1, "session_id":1}}
    ]
    run_pipeline(pipe1, "doc-vector (should return doc)")

# filter inside $vectorSearch i.e filter first then vector search
pipe2 = [
    {"$vectorSearch": {
        "index": INDEX_NAME,
        "queryVector": q0,
        "path": "embedding",
        "k": 5,
        "numCandidates": numCandidates,
        "limit": limit,
        "filter": {"session_id" : "testsession2"}
    }},
    {"$project": {"_id":1, "text":1, "source":1, "session_id":1}}
]
run_pipeline(pipe2, "vector without session filter")

print("\n-- Done --")
