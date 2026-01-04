from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from logger import logger
from modules.pdf_handlers import save_uploaded_files
from mongodb.vector_ingest import ingest_files_to_mongo
from modules.verify_session import verify_and_initialize_session
from auth.dependencies import get_current_user_optional
from fastapi import Depends
from global_modules.pg_pool import get_pg_pool,close_pg_pool
from datetime import datetime
from contextlib import asynccontextmanager

# import routers
from api.rag_router import router as rag_router
from api.auth_router import router as auth_router
from api.chats_router import router as chats_router
from api.home import router as home_router
from api.load_transcript_router import router as transcripts_router
from api.upload_router import router as upload_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Logic ---
    logger.info("🔰 Starting up: Initializing resources...")
    await get_pg_pool() 
    
    yield  # The server is now running and "yielding" control to requests
    
    # --- Shutdown Logic ---
    logger.info("Shutting down: Cleaning up resources...")
    await close_pg_pool()


app = FastAPI(title="DocTubeAI Server", version="1.0.0",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(home_router)
app.include_router(transcripts_router)
app.include_router(upload_router)

@app.middleware("http")
async def catch_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.exception("Unhandled Exception")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
   