import os
from dotenv import load_dotenv
load_dotenv()

from motor.motor_asyncio import AsyncIOMotorClient
MONGODB_URI = os.getenv("MONGODB_URI_STRING")
_MONGO_CLIENT = AsyncIOMotorClient(os.getenv("MONGODB_URI_STRING"))

collection = _MONGO_CLIENT["rag_db"]["documents"]