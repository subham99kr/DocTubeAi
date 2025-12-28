# complete this file
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
import logging
from mongodb.insert_chunks import insert_chunks
from modules.pdf_handlers import delete_local_files

load_dotenv()
logger = logging.getLogger(__name__)

from modules.load_and_split_with_ocr import load_and_split_with_ocr

def ingest_files_to_mongo(
    file_paths: List[str],
    session_id: str,
    user_id: Optional[str] = None,
    keep_local: bool = False,
) -> Dict[str, Any]:
    """
    Ingest multiple file using their paths into MongoDB Atlas Vector Search.
    Returns a summary dict with per-file chunk counts.
    """
    if not file_paths:
        return {"status": "no_files", "files": []}

    # 1) split into chunks
    logger.info("Loading and splitting %d files...", len(file_paths))
    chunks = load_and_split_with_ocr(file_paths,session_id=session_id)

    if not chunks:
        return {"status": "no_chunks", "chunks_inserted": 0}

    # 2) insert chunks into MongoDB in batches
    try:
        logger.info("calling insert_chunks function")
        insert_chunks(chunks)
        logger.info("insert_chunks function completed")

    
        # 3) now cleaning up local files
        if not keep_local:
            delete_local_files(file_paths)
            logger.info("Deleted local files after ingestion.")
        
        return {
        "status": "ingest_complete",
        }
    except Exception as e:
        logger.exception("Ingestion failed: %s", e)
        return {"status": "ingest_failed"}
    
