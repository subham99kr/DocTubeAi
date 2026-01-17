from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import logging
from mongodb.insert_chunks import insert_chunks
from modules.pdf_handlers import delete_local_files, delete_session_directory
from modules.load_and_split_with_ocr import load_and_split_with_ocr

load_dotenv()
logger = logging.getLogger(__name__)

async def ingest_files_to_mongo(
    file_paths: List[str],
    session_id: str,
    user_id: Optional[str] = None,
    keep_local: bool = False,
) -> Dict[str, Any]:
    """
    Ingest multiple files into MongoDB Atlas Vector Search.
    Fix: Directly await insert_chunks instead of using run_in_threadpool.
    """
    if not file_paths:
        return {"status": "no_files", "files": []}

    # 1) Load and split into chunks
    logger.info("Loading and splitting %d files...", len(file_paths))
    chunks = await load_and_split_with_ocr(file_paths, session_id=session_id)

    if not chunks:
        logger.warning("No chunks generated from files.")
        return {"status": "no_chunks", "chunks_inserted": 0}

    # 2) Insert chunks into MongoDB
    try:
        logger.info("Calling async insert_chunks function for %d chunks", len(chunks))
        
        # FIX: await the async function directly. Do NOT use run_in_threadpool for Motor.
        await insert_chunks(chunks) 
        
        logger.info("insert_chunks function completed successfully")

        # 3) Cleanup local files
        if not keep_local:
            # We await these as they are defined as async in your pdf_handlers
            await delete_local_files(file_paths)
            await delete_session_directory(session_id)
            logger.info("🟢🗑️ Deleted local files and session directory after ingestion.")
        
        return {
            "status": "ingest_complete",
            "chunk_count": len(chunks),
            "session_id": session_id
        }

    except Exception as e:
        logger.exception("🔴 Ingestion failed: %s", e)
        return {"status": "ingest_failed", "error": str(e)}