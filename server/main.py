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
from contextlib import asynccontextmanager


app = FastAPI(title="DocTubeAI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag_router)

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
):
    try: 
        saved_paths = await save_uploaded_files(files, session_id)
        logger.info("Saved files: %s", saved_paths)
    except Exception as e:
        logger.exception("Error saving uploaded files")
        return JSONResponse(status_code=500, content={"error": str(e)})
            ## now if everything ok i.e I have saved files paths and can proceed to ingest

    try:
        result = await ingest_files_to_mongo(
            file_paths=saved_paths,
            session_id=session_id,
            keep_local= False,
        )
        ingest_status = result.get("status")
        
        return JSONResponse(status_code=200, content={"status":ingest_status})
    except Exception as e:
        logger.exception("Ingest failed: %s", e)
        # keep local files for debugging
        return JSONResponse(status_code=500, content={"error": str(e)})

    
   
@app.post("/load_transcript/")
async def load_transcripts_endpoint(
    url:str = Form(...) ,
    session_id : str = Form(...)):
    """
    Accepts a JSON body like:
    {
        "url": "https://www.youtube.com/watch?v=yyyy"
       
    }
    Extracts transcripts, stores them in Chroma.
    """
    try:
        logger.info(f"Received {url} YouTube URLs for transcript loading")
        load_transcript(url,session_id=session_id)
        logger.info("Transcripts added to vector db successfully")
        return JSONResponse(status_code=200, content={"message": "Transcripts processed and vectorstore updated"})
    except Exception as e:
        logger.exception("Error during transcript loading")
        return JSONResponse(status_code=500, content={"error": str(e)})



@app.get("/test")
async def test():
    return {"message": "Test successful!"}

@app.get("/create_new_session")
async def create_new_session():
    session_id = str(uuid.uuid4())
    return {"session_id",session_id}

