import os
import shutil
import aiofiles
import aiofiles.os  # i don't need this right now.. may require it later 
from fastapi.concurrency import run_in_threadpool
from fastapi import UploadFile
from pathlib import Path
from typing import List
import logging
import uuid
from global_modules.pg_pool import get_pg_pool

logger = logging.getLogger(__name__)

BASE_UPLOAD_DIR = "./uploaded_pdfs"


async def ensure_dir(path: str) -> None:
    """Run directory creation in a threadpool to avoid blocking."""
    def create():
        Path(path).mkdir(parents=True, exist_ok=True)
    await run_in_threadpool(create) 


async def unique_filepath(dest_dir: str, filename: str, session_id: str | None = None) -> str:
   
    dest = Path(dest_dir)
    if session_id:
        dest = dest/session_id
    
    await ensure_dir(str(dest))

    candidate = dest / filename
    # Check existence
    if await aiofiles.os.path.exists(str(candidate)):
        uniq = f"{Path(filename).stem}_{uuid.uuid4().hex[:6]}{Path(filename).suffix}"
        candidate = dest / uniq
    
    return str(candidate.resolve())

async def append_pdfs_to_db(session_id: str, filenames: List[str]):
    """
    appends a list of filenames to the pdfs_uploaded column in Postgres.
    """
    # pool from your singleton
    pool = await get_pg_pool()
    
    # array_cat merges the existing array with the new one.
    # COALESCE handles the edge case where the column might be NULL.
    query = """
        INSERT INTO sessions (session_id, pdfs_uploaded, created_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (session_id) 
        DO UPDATE SET 
            pdfs_uploaded = array_cat(COALESCE(sessions.pdfs_uploaded, '{}'), EXCLUDED.pdfs_uploaded);
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (session_id,filenames))

            await conn.commit()   # because of this the db table was not populating
                # Connection context manager automatically commits if no exception occurs
        logger.info(f"🟢Successfully appended {len(filenames)} files to session {session_id}")
    except Exception as e:
        logger.error(f"🔴Failed to update sessions table: {e}", exc_info=True)


async def save_uploaded_files(files: List[UploadFile], session_id: str) -> List[str]:
    """
    Save UploadFile objects to disk (streamed), return list of saved file paths.
    Supports multiple files.
    """
    await ensure_dir(BASE_UPLOAD_DIR)
    saved_path: List[str] = []
    filenames_to_db: List[str] = []

    for upload in files:
        # ensure pointer is at start
        await upload.seek(0)
        

        safe_path = await unique_filepath(BASE_UPLOAD_DIR, upload.filename, session_id=session_id)
        # with open(safe_path, "wb") as out_f: # this is sync. and its breaking my code
        #     # stream copy
        #     shutil.copyfileobj(upload.file, out_f)  # this is sync. and its breaking my code

        async with aiofiles.open(safe_path, "wb") as out_f:
            while content := await upload.read(1024 * 1024):  # Read in chunks of 1 MB
                await out_f.write(content)

        await upload.seek(0)

        saved_path.append(safe_path)
        filenames_to_db.append(upload.filename)

        # close underlying file
        try:
            await upload.close()
        except Exception:
            pass
        
        logger.info("🟢Saved upload to %s", safe_path)

    if filenames_to_db:
        await append_pdfs_to_db(session_id, filenames_to_db)

    return saved_path


async def delete_local_files(paths: List[str]) -> None:
    """Delete files asynchronously without blocking the loop."""
    for p in paths:
        try:
            if await aiofiles.os.path.exists(p):
                await aiofiles.os.remove(p)
                logger.info(f"🟢 Deleted: {p}")
        except Exception as e:
            logger.error(f"🔴 Failed to delete {p}: {e}")

async def delete_session_directory(session_id: str) -> None:
    """Deletes the entire directory for a session and all its contents."""
    session_path = Path(BASE_UPLOAD_DIR) / session_id
    
    if session_path.exists() and session_path.is_dir():
        try:
            # shutil.rmtree is blocking, so we run it in the threadpool
            await run_in_threadpool(shutil.rmtree, str(session_path))
            logger.info(f"🟢 Successfully cleaned up folder for session: {session_id}")
        except Exception as e:
            logger.error(f"🔴 Failed to delete session folder {session_id}: {e}")