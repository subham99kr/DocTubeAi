import os
from dotenv import load_dotenv
load_dotenv()

# Backend FastAPI base URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
PUBLIC_BACKEND_URL = os.getenv("PUBLIC_BACKEND_URL")
