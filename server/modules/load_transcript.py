import os
import logging
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from .get_transcript import transcrpition_extractor,get_video_title
from mongodb.insert_chunks import insert_chunks


from dotenv import load_dotenv
load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def load_transcript(
    youtube_url: str,
    session_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    raise_on_empty: bool = False,
):
    
    

    # 1) get transcript text and video title
    try:
         transcript_text = transcrpition_extractor(youtube_url)
         source = get_video_title(youtube_url)
         
    except Exception as exc:
        logger.warning("Failed to fetch transcript for %s: %s", youtube_url, exc)
        if raise_on_empty:
            raise
        return None

    if not transcript_text or not transcript_text.strip():
        msg = f"Empty transcript for {youtube_url}"
        logger.warning(msg)
        if raise_on_empty:
            raise ValueError(msg)
        return None

    # 2) wrap as a Document
    doc = Document(
        page_content=transcript_text,
        metadata={
            "source": source,
            "session_id": session_id,
        },
    )

    # 3) split into chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents([doc])

    # 4) send this chunks to insert_chunks
    logger.info("calling insert_chunks function for transcript chunks")
    insert_chunks(chunks)
    logger.info("insert_chunks function completed for transcript chunks")
    

