# pdf_handler.py --- complete this file
import os
import shutil
from fastapi import UploadFile
from pathlib import Path
from typing import List
import logging
import uuid

logger = logging.getLogger(__name__)

BASE_UPLOAD_DIR = "./uploaded_pdfs"


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def unique_filepath(dest_dir: str, filename: str, session_id: str | None = None) -> str:
    """
    Create a safe unique filepath.
    If session_id provided, create a subfolder for that session.
    """
    dest = Path(dest_dir)
    if session_id:
        dest = dest / session_id
    ensure_dir(str(dest))

    # make filename safe by adding uuid if needed
    candidate = dest / filename
    if candidate.exists():
        uniq = f"{Path(filename).stem}_{uuid.uuid4().hex[:6]}{Path(filename).suffix}"
        candidate = dest / uniq
    return str(candidate.resolve())


def save_uploaded_files(files: List[UploadFile], session_id: str) -> List[str]:
    """
    Save UploadFile objects to disk (streamed), return list of saved file paths.
    Supports multiple files.
    """
    ensure_dir(BASE_UPLOAD_DIR)
    saved: List[str] = []
    for upload in files:
        # ensure pointer is at start
        try:
            upload.file.seek(0)
        except Exception:
            pass

        safe_path = unique_filepath(BASE_UPLOAD_DIR, upload.filename, session_id=session_id)
        with open(safe_path, "wb") as out_f:
            # stream copy
            shutil.copyfileobj(upload.file, out_f)

        saved.append(safe_path)

        # close underlying file
        try:
            upload.file.close()
        except Exception:
            pass

        logger.info("Saved upload to %s", safe_path)
    return saved


def delete_local_files(paths: List[str]) -> None:
    """
    Delete local files if they exist. Logs but does not raise on error.
    """
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
                logger.info("Deleted local file %s", p)
        except Exception as e:
            logger.exception("Failed to delete %s: %s", p, e)

