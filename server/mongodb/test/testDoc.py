import os

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.environ.get("MONGODB_URI_STRING")
client = MongoClient(uri)
coll = client["rag_db"]["documents"]

doc = {
    "_id": "testsession::test.pdf::0",
    "session_id": "testsession",
    "source": "test.pdf",
    "text": "hello vector",
    "embedding": [0.5] * 384   # use your embedding dim
}
coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)
print("Inserted test doc")
