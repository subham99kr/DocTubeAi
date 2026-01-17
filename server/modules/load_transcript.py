
import logging
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from global_modules.pg_pool import get_pg_pool

from modules.get_transcript import transcrpition_extractor, get_video_title
from mongodb.insert_chunks import insert_chunks
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

import json

async def append_link_to_db(session_id: str, url: str, title: str):
    """
    Appends a single {url, title} object to the url_links JSONB column in Postgres.
    """
    pool = await get_pg_pool()
    
    # We wrap the single dict in a list [] so the || operator 
    # performs an array concatenation in Postgres.
    new_link = {
        "url": url, 
        "title": title,
        "added_at": datetime.now().isoformat()
    }
    
    new_link_json = json.dumps(new_link)

    query = """
        INSERT INTO sessions (session_id, url_links, created_at, last_activity)
        VALUES (
            %s, 
            jsonb_build_array(%s::jsonb), 
            NOW(), 
            NOW()
        )
        ON CONFLICT (session_id) 
        DO UPDATE SET 
            url_links = COALESCE(sessions.url_links, '[]'::jsonb) || jsonb_build_array(%s::jsonb),
            last_activity = NOW();
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (session_id, new_link_json, new_link_json))
            await conn.commit()
            
        logger.info(f"🟢 Successfully appended link to session {session_id}: {title}")
    except Exception as e:
        logger.error(f"🔴 Failed to update sessions table for link: {e}", exc_info=True)

async def load_transcript(
    youtube_url: str,
    session_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 100, 
    raise_on_empty: bool = False,
) -> Optional[bool]:
    
    try:
        # 1) Fetch data in threadpool to avoid blocking the event loop
        # We run these together as a single blocking task or separately
        text = await transcrpition_extractor(youtube_url)
        title = await get_video_title(youtube_url)

         
    except Exception as exc:
        logger.warning("Failed to fetch transcript for %s: %s", youtube_url, exc)
        if raise_on_empty:
            raise
        return None

    if not text or not text.strip():
        msg = f"Empty transcript for {youtube_url}"
        logger.warning(msg)
        if raise_on_empty:
            raise ValueError(msg)
        return None

    # 2) Wrap as a Document
    doc = Document(
        page_content=text,
        metadata={
            "source": title,
            "session_id": session_id,
        },
    )

    # 3) Split into chunks (CPU bound, usually fast enough to stay sync)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = splitter.split_documents([doc])

    # 4) Send chunks to MongoDB (IO bound)
    logger.info("🔰 Calling insert_chunks function for transcript chunks")
    await insert_chunks(chunks)
    logger.info("🟢 insert_chunks function completed for transcript chunks")

    await append_link_to_db(session_id, youtube_url, title)
    
    return title