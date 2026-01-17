# from deep_translator import GoogleTranslator
# from langdetect import detect
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from fastapi import HTTPException
import logging
from global_modules.http_client import get_http_client

# Import your client manager (adjust the import path as needed)
# from global_modules.http_client import get_http_client 

logger = logging.getLogger(__name__)

def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        qs = parse_qs(parsed.query)
        return qs.get("v", [None])[0]
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    return None

# def to_english(text: str) -> str:
#     text = text.strip()
#     if not text:
#         return text
#     try:
#         sample = text[:1000]
#         lang = detect(sample)
#     except Exception:
#         lang = "en"

#     if lang == "en":
#         return text

#     translator = GoogleTranslator(source="auto", target="en")
#     max_chunk_size = 4000
#     translated_parts = []
#     start = 0

#     while start < len(text):
#         chunk = text[start:start + max_chunk_size]
#         try:
#             translated_chunk = translator.translate(chunk)
#         except Exception:   
#             return text
#         translated_parts.append(translated_chunk)
#         start += max_chunk_size

#     return " ".join(translated_parts)

async def get_video_title(url: str) -> str:
    """
    Fetches the title of the YouTube video using the singleton httpx client.
    """
    try:
        # Get your singleton client
        client = await get_http_client()
        
        # Use httpx to fetch the title asynchronously
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        
        html_content = response.text
        title = html_content.split('<title>')[1].split('</title>')[0].replace("- YouTube", "").strip()
        return title
    except Exception as e:
        logger.error(f"🔴 could not retrieve title from url-{url}: {e}")
        # Returning a placeholder instead of crashing ensures the transcript can still load
        return "Unknown YouTube Video"

async def transcrpition_extractor(url: str) -> str :
    video_id = _extract_video_id(url)
    if not video_id:
        logger.info(f"Could not extract video ID from URL: {url!r}")
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        # 1) Get the title asynchronously
        title = await get_video_title(url)

        # 2) Fetch transcript
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=[
            "en", "hi", "de", "fr", "es", "it", "ru", "zh", "ja", "ko",
            "ar", "pt", "tr", "nl", "sv", "pl", "uk", "ro", "cs", "el",
            "bn", "fa", "ur", "ta", "te", "ml", "kn"
        ]).to_raw_data()
        
        full_text = " ".join(
            piece["text"].replace("\n", " ")
            for piece in transcript
            if "text" in piece
        )

        # Prepend the title to the transcript text
        full_text_with_title = f"Video Title: {title}\n\nTranscript: {full_text}"

        # 3) Translate to English 
        text = full_text_with_title # = to_english(full_text_with_title)
        return text

    except (TranscriptsDisabled, NoTranscriptFound):
        raise HTTPException(status_code=404, detail="No transcript found or captions are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video is unavailable or private.")
    except Exception as e:
        logger.error(f"Unexpected error in extractor: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")