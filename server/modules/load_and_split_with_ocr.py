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
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
        percentage = (self.current / self.total) * 100 if self.total > 0 else 0
        return f"Processing: {self.current}/{self.total} ({percentage:.1f}%)"


def clean_text_for_vector_db(text: str) -> str:
    text = text.replace("\t", " ")           # Replace tabs with space
    text = re.sub(r"\s*\n\s*", " ", text)    # Replace newline with space
    text = re.sub(r" +", " ", text)          # Replace multiple spaces
    return text.strip()


async def _ocr_page(pdf_path: str, page_number: int, zoom: float = 1.5, lang: Optional[str] = None) -> str:
    if not OCR_AVAILABLE:
        logger.error("🔴 OCR requested but dependencies (fitz, PIL, or pytesseract) are missing.")
        return ""
    def blocking_ocr():
        try:
            with fitz.open(pdf_path) as doc:
                page = doc.load_page(page_number)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")

            with Image.open(io.BytesIO(img_bytes)) as img:
                img = img.convert("RGB")
                custom_config = r'--oem 3 --psm 6' 
                text = pytesseract.image_to_string(img, lang=lang, config=custom_config)
                return (text or "").strip()
        except Exception as e:
            logger.exception("OCR failed for %s page %d: %s", pdf_path, page_number, e)
            return ""
    return await run_in_threadpool(blocking_ocr)


async def _load_pdf(path: str) -> List[Any]:
    def _load():
        loader = PyPDFLoader(path)
        return loader.load()
    return await run_in_threadpool(_load)


def _fixed_size_split_docs(docs: List[SimpleDoc], chunk_size: int, chunk_overlap: int, session_id: str) -> List[Document]:
    """Uses LangChain's smart splitter to keep sentences and words intact."""
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        # Separators order: Paragraphs -> Sentences -> Words -> Characters
        separators=["\n\n", "\n", " ", ""] 
    )

    out: List[Document] = []

    for doc in docs:
        if not doc.page_content:
            continue
            
        src = doc.metadata.get("source", "unknown")
        
        # This split_text method handles the sliding window logic for you
        texts = splitter.split_text(doc.page_content)
        
        for t in texts:
            out.append(Document(
                page_content=t,
                metadata={
                    "session_id": session_id, 
                    "source": src
                }
            ))
            
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
    
    if isinstance(paths, str):
        paths = [paths]
    
    def get_total_pages():
        count = 0
        for p in paths:
            try:
                with fitz.open(p) as d:
                    count += d.page_count
            except Exception:
                continue
        return count

    total_pages = await run_in_threadpool(get_total_pages)
    tracker = ProgressTracker(total_pages)

    async def process_single_pdf(p):
        src_name = Path(p).name
        pdf_full_text = []

        try:
            loaded = await _load_pdf(p)

            # Normal Text extraction path
            if loaded:
                for page_index, doc in enumerate(loaded):
                    page_text = (getattr(doc, "page_content", "") or "").strip()

                    # Trigger OCR if text is sparse (scanned pages)
                    if OCR_AVAILABLE and len(page_text) < ocr_min_chars_threshold:
                        ocr_text = await _ocr_page(p, page_index, zoom=ocr_zoom, lang=ocr_lang)
                        if ocr_text and len(ocr_text) > len(page_text):
                            page_text = ocr_text
                    
                    pdf_full_text.append(clean_text_for_vector_db(page_text))
                    if progress_callback:
                        await progress_callback(tracker.update())

            # Pure Scanned PDF path (loader failed or returned nothing)
            elif OCR_AVAILABLE:
                def get_count():
                    with fitz.open(p) as d: return d.page_count
                count = await run_in_threadpool(get_count)

                for i in range(count):
                    ocr_text = await _ocr_page(p, i, zoom=ocr_zoom, lang=ocr_lang)
                    pdf_full_text.append(clean_text_for_vector_db(ocr_text))
                    if progress_callback:
                        await progress_callback(tracker.update())
                        
        except Exception as e:
            logger.exception("🔴 Failed to process PDF %s: %s", p, e)

        if pdf_full_text:
            # Join all pages with a newline to prevent mid-page fragmentation
            return [SimpleDoc(
                page_content="\n".join(pdf_full_text), 
                metadata={"source": src_name}
            )]
        return []

    # EXECUTE: Run PDF tasks in parallel
    results = await asyncio.gather(*(process_single_pdf(p) for p in paths))
    
    # Flatten results (results is a list of lists of SimpleDoc)
    all_docs = [doc for sublist in results for doc in sublist]

    # SPLIT: Perform the sliding window chunking on the long joined strings
    return _fixed_size_split_docs(all_docs, chunk_size, chunk_overlap, session_id)

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

