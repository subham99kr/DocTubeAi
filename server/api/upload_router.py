import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from modules.verify_session import verify_and_initialize_session
from auth.dependencies import get_current_user_optional
from modules.pdf_handlers import save_uploaded_files
from mongodb.vector_ingest import ingest_files_to_mongo

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/uploads",
    tags=["Uploads"]
)

@router.post("/pdfs")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    session_id: str = Form(...),
    oauth_id: Optional[str] = Depends(get_current_user_optional) 
):
    """
    Handles PDF uploads: saves locally, updates Postgres, and ingests to Vector DB.
    """
    if not files or all(f.filename.strip() == "" for f in files):
        raise HTTPException(status_code=400, detail="No files were uploaded.")
    
    uploaded_filenames = [f.filename for f in files if f.filename.strip() != ""]
    
    # 1. Security check
    await verify_and_initialize_session(session_id, oauth_id)
    
    try: 
        # 2. temporarly save files & Update Postgres
        saved_paths = await save_uploaded_files(files, session_id)
        
        # 3. Vector ingestion
        result = await ingest_files_to_mongo(
            file_paths=saved_paths,
            session_id=session_id,
            keep_local=False, # Deletes files after ingestion
        )
        
        return JSONResponse(
            status_code=200, 
            content={"status": result.get("status", "success"), "session_id": session_id, "filenames":uploaded_filenames}
        )

    except Exception as e:
        logger.exception("Upload or Ingestion failed")
        return JSONResponse(
            status_code=500, 
            content={"error": "An internal error occurred during file processing"}
        )