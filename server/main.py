from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from modules.load_transcript import load_transcript
from logger import logger
import uuid
from modules.pdf_handlers import save_uploaded_files, delete_local_files
from mongodb.vector_ingest import ingest_files_to_mongo
from api.rag_router import router as rag_router
from api.auth_router import router as auth_router
from modules.verify_session import verify_and_initialize_session
from auth.dependencies import get_current_user_optional
from fastapi import Depends
from global_modules.pg_pool import get_pg_pool
from datetime import datetime


app = FastAPI(title="DocTubeAI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router)
app.include_router(auth_router)

@app.middleware("http")
async def catch_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.exception("Unhandled Exception")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/upload_pdfs/")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    session_id: str = Form(...),
    # Securely get the user from the JWT header, not a form field
    oauth_id: str = Depends(get_current_user_optional) 
):
    await verify_and_initialize_session(session_id, oauth_id)
    
    try: 
        saved_paths = await save_uploaded_files(files, session_id)
        # Extract filenames to store in Postgres
        filenames = [f.filename for f in files]
        
        # 1. Update Postgres: Add filenames to array and refresh timestamp
        pool = await get_pg_pool()
        query = """
            UPDATE sessions 
            SET pdfs_uploaded = array_cat(pdfs_uploaded, %s),
                last_activity = NOW()
            WHERE session_id = %s AND (oauth_id = %s OR oauth_id IS NULL);
        """
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (filenames, session_id, oauth_id))
            await conn.commit()

        # 2. Proceed to Vector Ingest
        result = await ingest_files_to_mongo(
            file_paths=saved_paths,
            session_id=session_id,
            keep_local=False,
        )
        return JSONResponse(status_code=200, content={"status": result.get("status")})

    except Exception as e:
        logger.exception("Upload/Ingest failed")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
   
@app.post("/load_transcript/")
async def load_transcripts_endpoint(
    url: str = Form(...),
    session_id: str = Form(...),
    oauth_id: str = Depends(get_current_user_optional)
):
    await verify_and_initialize_session(session_id, oauth_id)
    try:
        await load_transcript(url, session_id=session_id)
        
        # Update Postgres: Add URL to the jsonb list
        pool = await get_pg_pool()
        new_link = {"url": url, "added_at": str(datetime.now())}
        
        query = """
            UPDATE sessions 
            SET url_links = url_links || %s::jsonb,
                last_activity = NOW()
            WHERE session_id = %s;
        """
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                import json
                await cur.execute(query, (json.dumps([new_link]), session_id))
            await conn.commit()

        return JSONResponse(status_code=200, content={"status": "Success"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})