from deep_translator import GoogleTranslator
from langdetect import detect
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
import requests

def _extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)

    # Standard YouTube URLs
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        qs = parse_qs(parsed.query)
        return qs.get("v", [None])[0]

    # Short youtu.be URLs
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")

    return None


# most probably this won't work as google blocks req. from sites like aws, azure, collab..
# use llm to translate it to english --will implement if this doesn't work

def to_english(text: str) -> str:
    """
    Auto-detects language and returns English text.
    - Skips translation if already English.
    - Splits long text into chunks.
    - If translation fails, returns original text.
    """
    text = text.strip()
    if not text:
        return text

    try:
        sample = text[:1000]
        lang = detect(sample)
    except Exception:
        lang = "en"

    if lang == "en":
        return text

    translator = GoogleTranslator(source="auto", target="en")
    max_chunk_size = 4000
    translated_parts = []
    start = 0

    while start < len(text):
        chunk = text[start:start + max_chunk_size]
        try:
            translated_chunk = translator.translate(chunk)
        except Exception:   
            return text
        translated_parts.append(translated_chunk)
        start += max_chunk_size

    return " ".join(translated_parts)



def get_video_title(url: str) -> str:
    """
    Fetches the title of the YouTube video at `url`.
    """
    try:
        response = requests.get(url, timeout=5)
        html_content = response.text
        title = html_content.split('<title>')[1].split('</title>')[0].replace("- YouTube", "").strip()
        return title
    except Exception as e:
        raise RuntimeError(f"Could not retrieve title for URL {url}: {e}") from e

def transcrpition_extractor(url: str) -> str :
    """
    Return the transcription text of the YouTube video at `url` in English.

    - Extracts the video ID from the URL.
    - Tries to fetch English transcript directly.
    - If English is not available, fetches any transcript and translates it to English.
    - Concatenates all text segments into a single string.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url!r}")

    try:
        # 1)lets get the title of the video
        title = get_video_title(url)

        # 2) try to fetch English transcript directly
        transcript = YouTubeTranscriptApi().fetch(video_id,languages=["en", "hi", "de", "fr", "es", "it", "ru", "zh", "ja", "ko","ar", "pt", "tr", "nl", "sv", "pl", "uk", "ro", "cs", "el",
        "bn", "fa", "ur", "ta", "te", "ml", "kn"]).to_raw_data()
        full_text = f"This transcript is from the video titled : {title} ".join(
            piece["text"].replace("\n", " ")
            for piece in transcript
            if "text" in piece
        )

        # 3) Translate to English 
        text = to_english(full_text)
        return text

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
        raise RuntimeError(f"Could not retrieve transcript for video {video_id}: {e}") from e

