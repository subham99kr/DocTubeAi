from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from logger import logger
from global_modules.pg_pool import get_pg_pool,close_pg_pool
from contextlib import asynccontextmanager

# routers
from api.chatting_router import router as chatting_router
from api.auth_router import router as auth_router
from api.load_chats_router import router as load_chats_router
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

app.include_router(chatting_router)
app.include_router(auth_router)
app.include_router(load_chats_router)
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
    
   