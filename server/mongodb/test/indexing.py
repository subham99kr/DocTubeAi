from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()

uri = os.environ.get("MONGODB_URI_STRING")

client = MongoClient(uri)
db = client["rag_db"]
coll = db["documents"]

# create scalar index for fast session filtering & deletions
coll.create_index([("session_id", 1)], name="idx_session_id", background=True)
print("session_id index ensured")
