# load_and_split_with_ocr.py
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable
import logging
from dataclasses import dataclass
from langchain_core.documents import Document

from langchain_community.document_loaders import PyPDFLoader

logger = logging.getLogger(__name__)

# Optional OCR imports
try:
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    fitz = None
    Image = None
    pytesseract = None
    OCR_AVAILABLE = False
import re

def clean_text_for_vector_db(text: str) -> str:
    # Replace newlines and tabs with space
    text = text.replace("\t", " ")
    text = re.sub(r"\s*\n\s*", " ", text)
    # Collapse multiple spaces
    text = re.sub(r" +", " ", text)
    return text.strip()

@dataclass
class SimpleDoc:
    page_content: str
    metadata: Dict[str, Any]


def _ocr_page_with_fitz(pdf_path: str, page_number: int, zoom: float = 1.5, lang: Optional[str] = None) -> str:
    """
    Render one PDF page with PyMuPDF and run pytesseract OCR on it.
    Returns recognized text (may be empty string).
    """
    if not OCR_AVAILABLE:
        return ""

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


def _ensure_paths(paths_or_path: Optional[Iterable[str]]) -> List[str]:
    """
    Accept either a single path string or an iterable of paths and
    return a list of string paths.
    """
    if paths_or_path is None:
        return []
    # If a single string was passed, wrap it
    if isinstance(paths_or_path, str):
        return [paths_or_path]
    return [str(p) for p in paths_or_path]


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


def load_and_split_with_ocr(
    paths: List[str] | str,
    session_id: str,
    user_id: Optional[str] = None,  # not doing this right now
    chunk_size: int = 1000,
    chunk_overlap: int = 100,
    ocr_min_chars_threshold: int = 40,
    ocr_zoom: float = 1.2,
    ocr_lang: Optional[str] = None,
) -> List[Document]:
    """
    Load PDFs, optionally OCR low-text pages, then split into fixed-size chunks.
    Each returned chunk is a dict: {"text": ..., "metadata": {"session_id": ..., "source": <pdf_name>}}

    Notes:
    - `paths` may be a single path string or a list of path strings.
    - Only `session_id` and `source` are kept in each chunk's metadata (as requested).
    """
    # normalize inputs
    paths_list = _ensure_paths(paths)
    session_id = str(session_id)

    all_docs: List[SimpleDoc] = []

    for p in paths_list:
        p = str(p)
        src_name = Path(p).name

        # Try native text extraction with PyPDFLoader
        try:
            loader = PyPDFLoader(p)
            loaded = loader.load()  # typically list of Document-like objects
        except Exception as e:
            logger.exception("Failed to load PDF %s with PyPDFLoader: %s", p, e)
            loaded = []

        # If loader returned docs, iterate them; else we may fallback to OCR for all pages
        if loaded:
            for page_index, doc in enumerate(loaded):
                # robust extraction: Document objects usually have .page_content; some loaders return dicts
                page_text = getattr(doc, "page_content", None)
                if page_text is None and isinstance(doc, dict):
                    page_text = doc.get("text", "") or doc.get("page_content", "")
                page_text = (page_text or "").strip()

                # Decide to OCR only if OCR is available AND extracted text is short
                ocr_used = False
                if OCR_AVAILABLE and len(page_text) < ocr_min_chars_threshold:
                    try:
                        ocr_text = _ocr_page_with_fitz(p, page_index, zoom=ocr_zoom, lang=ocr_lang)
                        if ocr_text and len(ocr_text.strip()) > len(page_text):
                            page_text = ocr_text.strip()
                            ocr_used = True
                    except Exception:
                        logger.exception("OCR attempt failed for %s page %d", p, page_index)
                        ocr_used = False

                # Build a SimpleDoc. We include source inside the metadata for the splitter helper to pick up.
                per_page_meta = {"source": src_name, "ocr_used": ocr_used}
                page_text = clean_text_for_vector_db(page_text)
                all_docs.append(SimpleDoc(page_content=page_text, metadata=per_page_meta))
        else:
            # Fallback: OCR every page if loader returned nothing and OCR is available
            if OCR_AVAILABLE:
                try:
                    with fitz.open(p) as pdf_doc:
                        for page_index in range(pdf_doc.page_count):
                            page_text = _ocr_page_with_fitz(p, page_index, zoom=ocr_zoom, lang=ocr_lang)
                            per_page_meta = {"source": src_name, "ocr_used": True}
                            all_docs.append(SimpleDoc(page_content=page_text, metadata=per_page_meta))
                except Exception as e:
                    logger.exception("Full PDF OCR fallback failed for %s: %s", p, e)
            else:
                # no extracted pages and no OCR — continue
                logger.warning("No text extracted and OCR not available for %s", p)

    # Now split into fixed-size chunks with overlap, preserving only session_id and source
    dict_chunks = _fixed_size_split_docs(all_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap, session_id=session_id)

    document_chunks = [
        Document(
            page_content=d["text"],
            metadata=d["metadata"]
        ) 
        for d in dict_chunks
    ]
    return document_chunks

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

