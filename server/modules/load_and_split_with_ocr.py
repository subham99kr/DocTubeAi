import asyncio
import io
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable
from dataclasses import dataclass
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# Optional OCR imports
try:
    import fitz  # PyMuPDF
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    fitz = None
    Image = None
    pytesseract = None
    OCR_AVAILABLE = False

@dataclass
class SimpleDoc:
    page_content: str
    metadata: Dict[str, Any]

class ProgressTracker:
    def __init__(self, total_pages: int):
        self.total = total_pages
        self.current = 0

    def update(self):
        self.current += 1
        percentage = (self.current / self.total) * 100
        return f"Processing: {self.current}/{self.total} ({percentage:.1f}%)"


def clean_text_for_vector_db(text: str) -> str:
    text = text.replace("\t", " ")          # Replace tabs with space
    text = re.sub(r"\s*\n\s*", " ", text)   # Replace newline with space
    text = re.sub(r" +", " ", text)         # replace multiple spaces with single space
    return text.strip()                     # trim start and end spaces


async def _ocr_page(pdf_path: str, page_number: int, zoom: float = 1.5, lang: Optional[str] = None) -> str:
    """
    Render one PDF page with PyMuPDF and run pytesseract OCR on it.
    Returns recognized text (may be empty string).
    """
    if not OCR_AVAILABLE:
        return ""
    def blocking_ocr() :
        try:
            with fitz.open(pdf_path) as doc:
                page = doc.load_page(page_number)  # zero-based
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")

            with Image.open(io.BytesIO(img_bytes)) as img:
                img = img.convert("RGB")
                ocr_kwargs = {}
                if lang:
                    ocr_kwargs["lang"] = lang
                text = pytesseract.image_to_string(img, **ocr_kwargs)
                return (text or "").strip()
        except Exception as e:
            logger.exception("OCR failed for %s page %d: %s", pdf_path, page_number, e)
            return ""
    return await run_in_threadpool(blocking_ocr)


async def _load_pdf_async(path: str) -> List[Any]:
    """Runs the blocking PyPDFLoader in a separate thread."""
    def _load():
        loader = PyPDFLoader(path)
        return loader.load()
    return await run_in_threadpool(_load)


def _fixed_size_split_docs(
    docs: Iterable[SimpleDoc],
    chunk_size: int,
    chunk_overlap: int,
    session_id: str,
) -> List[Document]:
    """
    Split each doc.page_content into fixed-size character windows.
    Each returned chunk dict has {"text": ..., "metadata": {"session_id": ..., "source": ...}}
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    step = chunk_size - chunk_overlap
    out: List[Document] = []

    for doc in docs:
        text = (getattr(doc, "page_content", None) or "")
        if not text:
            continue  # skip empty pages

        # prefer metadata.source if present
        src = None
        meta = getattr(doc, "metadata", None)
        if isinstance(meta, dict):
            src = meta.get("source")
        # fallback to unknown
        if not src:
            src = "unknown"

        text_len = len(text)
        start = 0
        while start < text_len:
            end = start + chunk_size
            chunk_text = text[start:end]
            # final chunk could be shorter; we still include it
            chunk_meta = {"session_id": session_id, "source": src}
            out.append({"text": chunk_text, "metadata": chunk_meta})
            start += step

    return out

async def load_and_split_with_ocr(
    paths: List[str] | str,
    session_id: str,  
    progress_callback: Optional[callable] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    ocr_min_chars_threshold: int = 40,
    ocr_zoom: float = 1.2,
    ocr_lang: Optional[str] = None,
) -> List[Document]:
    # Normalize inputs
    if isinstance(paths, str):
        paths = [paths]
    
    def get_total_pages():
        count = 0
        for p in paths:
            with fitz.open(p) as d:
                count += d.page_count
        return count

    total_pages = await run_in_threadpool(get_total_pages)
    tracker = ProgressTracker(total_pages)

    # Create a list of tasks to process PDFs in parallel
    async def process_single_pdf(p):
        src_name = Path(p).name
        local_docs = []

        try:
            loaded = await _load_pdf_async(p)
        except Exception as e:
            logger.exception("🔴 Failed to load PDF %s: %s", p, e)
            loaded = []

        if loaded:
            for page_index, doc in enumerate(loaded):
                page_text = getattr(doc, "page_content", "") or ""
                page_text = page_text.strip()

                ocr_used = False
                if OCR_AVAILABLE and len(page_text) < ocr_min_chars_threshold:
                    ocr_text = await _ocr_page(p, page_index, zoom=ocr_zoom, lang=ocr_lang)
                    if ocr_text and len(ocr_text) > len(page_text):
                        page_text = ocr_text
                        ocr_used = True

                local_docs.append(SimpleDoc(
                    page_content=clean_text_for_vector_db(page_text), 
                    metadata={"source": src_name, "ocr_used": ocr_used}
                ))
                
                # --- UPDATE PROGRESS HERE ---
                if progress_callback:
                    status = tracker.update()
                    await progress_callback(status)
                    
        elif OCR_AVAILABLE:
            def get_count():
                with fitz.open(p) as d: return d.page_count
            count = await run_in_threadpool(get_count)

            for i in range(count):
                ocr_text = await _ocr_page(p, i, zoom=ocr_zoom, lang=ocr_lang)
                local_docs.append(SimpleDoc(
                    page_content=clean_text_for_vector_db(ocr_text), 
                    metadata={"source": src_name, "ocr_used": True}
                ))
                
                # --- UPDATE PROGRESS HERE TOO ---
                if progress_callback:
                    status = tracker.update()
                    await progress_callback(status)
                    
        return local_docs

    # Run all PDF extractions concurrently
    results = await asyncio.gather(*(process_single_pdf(p) for p in paths))
    
    # Flatten the list of lists
    all_docs = [doc for sublist in results for doc in sublist]

    # Split into chunks
    return _fixed_size_split_docs(all_docs, chunk_size, chunk_overlap, session_id)

def _fixed_size_split_docs(docs: List[SimpleDoc], chunk_size: int, chunk_overlap: int, session_id: str) -> List[Document]:
    """Helper for splitting - logic remains synchronous as it's pure string manipulation."""
    step = chunk_size - chunk_overlap
    out: List[Document] = []

    for doc in docs:
        text = doc.page_content
        if not text: continue

        src = doc.metadata.get("source", "unknown")
        text_len = len(text)
        start = 0
        while start < text_len:
            end = start + chunk_size
            chunk_text = text[start:end]
            out.append(Document(
                page_content=chunk_text,
                metadata={"session_id": session_id, "source": src}
            ))
            start += step
            if start >= text_len: break
            
    return out

# chunks format:
# { 
#    {"text": ..., 
#       "metadata": { 
#                       "session_id": ...,
#                       "source": ... 
#                    }
#    },
#
#    {"text": ..., 
#       "metadata": { 
#                       "session_id": ...,
#                       "source": ... 
#                    }
#    },...
#
#}

