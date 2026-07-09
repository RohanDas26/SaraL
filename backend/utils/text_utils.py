"""
utils/text_utils.py — Text extraction, cleaning, and chunking.

Supports PDF (PyMuPDF), DOCX (python-docx), and plain TXT (chardet encoding detection).

Extraction is page-aware: each page's text is tracked separately so that
chunk metadata can store an accurate source page number.

Chunking strategy:
  - Target size: 512 characters (≈ 128 tokens, well within context window)
  - Overlap:     64 characters
  - Boundary priority: paragraph → sentence → word → hard cut
  - Minimum chunk: 80 characters (discards headers, page numbers, noise)

No external NLP libraries.  No LangChain.
"""

import re
from typing import Optional

import fitz           # PyMuPDF
from docx import Document as DocxDocument
import chardet

from backend.config import Config
from backend.utils.logger import get_logger

log = get_logger(__name__)

# Minimum characters for a chunk to be kept
_MIN_CHUNK_CHARS = 80


# ══════════════════════════════════════════════════════════════════════
# TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════

def extract_text_from_pdf(file_path: str) -> tuple[str, int, list[tuple[int, int]]]:
    """
    Extract text from a PDF file page by page.

    Returns:
        full_text:   All pages joined with double newlines.
        page_count:  Total number of pages.
        page_map:    List of (char_start, page_number) tuples — used to assign
                     source page numbers to chunks.
    """
    parts: list[str] = []
    page_map: list[tuple[int, int]] = []
    char_pos = 0

    try:
        with fitz.open(file_path) as doc:
            page_count = len(doc)
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                if text.strip():
                    page_map.append((char_pos, page_num))
                    parts.append(text)
                    char_pos += len(text) + 2   # +2 for the joining "\n\n"

    except Exception as exc:
        raise ValueError(f"Failed to read PDF: {exc}") from exc

    full_text = "\n\n".join(parts)
    log.debug("PDF extracted: %d pages, %d characters", page_count, len(full_text))
    return full_text, page_count, page_map


def extract_text_from_docx(file_path: str) -> tuple[str, int, list[tuple[int, int]]]:
    """
    Extract text from a DOCX file.

    Returns:
        full_text, estimated_page_count, page_map
    Page numbers are estimated (DOCX has no hard page boundaries).
    """
    try:
        doc = DocxDocument(file_path)
    except Exception as exc:
        raise ValueError(f"Failed to read DOCX: {exc}") from exc

    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text  = "\n".join(paragraphs)

    # Estimate: ~300 words per page
    word_count      = len(full_text.split())
    estimated_pages = max(1, word_count // 300)

    # Build a simple page map: every ~300-word block = one page
    page_map        = _build_word_page_map(paragraphs)

    log.debug("DOCX extracted: ~%d pages, %d characters", estimated_pages, len(full_text))
    return full_text, estimated_pages, page_map


def extract_text_from_txt(file_path: str) -> tuple[str, int, list[tuple[int, int]]]:
    """
    Extract text from a plain text file with auto-detected encoding.

    Returns:
        full_text, estimated_page_count, page_map
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
    except Exception as exc:
        raise ValueError(f"Failed to read TXT: {exc}") from exc

    detected   = chardet.detect(raw)
    encoding   = detected.get("encoding") or "utf-8"
    confidence = detected.get("confidence", 0.0)
    log.debug("TXT encoding detected: %s (confidence %.2f)", encoding, confidence)

    full_text       = raw.decode(encoding, errors="replace")
    word_count      = len(full_text.split())
    estimated_pages = max(1, word_count // 300)

    # Single-block page map (no real page boundaries in plain text)
    page_map = [(0, 1)]

    log.debug("TXT extracted: ~%d pages, %d characters", estimated_pages, len(full_text))
    return full_text, estimated_pages, page_map


def extract_text(
    file_path: str,
    file_type: str,
) -> tuple[str, int, list[tuple[int, int]]]:
    """
    Dispatch to the correct extractor based on file_type.

    Returns:
        (full_text, page_count, page_map)
    """
    if file_type == "pdf":
        return extract_text_from_pdf(file_path)
    elif file_type == "docx":
        return extract_text_from_docx(file_path)
    elif file_type == "txt":
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: '{file_type}'")


# ══════════════════════════════════════════════════════════════════════
# TEXT CLEANING
# ══════════════════════════════════════════════════════════════════════

def clean_text(text: str) -> str:
    """
    Normalise and clean extracted text.

    Operations (order matters):
      1. Normalise line endings to \\n
      2. Remove non-printable characters (control chars) except \\t and \\n
      3. Collapse 3+ consecutive newlines → 2 (preserve paragraph breaks)
      4. Collapse multiple spaces/tabs on a single line → one space
      5. Strip leading/trailing whitespace per line
      6. Remove lines that are only punctuation or numbers (page artifacts)
    """
    # 1. Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Strip non-printable control characters (keep \t and \n)
    text = re.sub(r"[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]", " ", text)

    # 3. Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Collapse horizontal whitespace within lines
    text = re.sub(r"[ \t]{2,}", " ", text)

    # 5. Strip per-line
    lines = [line.strip() for line in text.split("\n")]

    # 6. Drop artifact-only lines (e.g. "- 3 -", "* * *", lone page numbers)
    cleaned_lines = []
    for line in lines:
        stripped = line.strip("- *•·\t ")
        # Keep the line unless it's blank or looks like a page artifact
        if stripped and not re.fullmatch(r"[\d\s\-\|–—]+", stripped):
            cleaned_lines.append(line)
        elif not stripped:
            cleaned_lines.append("")   # preserve blank lines for paragraph spacing

    text = "\n".join(cleaned_lines).strip()
    return text


# ══════════════════════════════════════════════════════════════════════
# CHUNKING
# ══════════════════════════════════════════════════════════════════════

def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> list[str]:
    """
    Split cleaned text into overlapping chunks.

    Boundary priority (highest to lowest):
      1. Paragraph boundary (double newline)
      2. Sentence boundary  (. ? !)
      3. Word boundary      (space)
      4. Hard cut           (last resort)

    Chunks shorter than _MIN_CHUNK_CHARS are discarded as noise.

    Returns a list of non-empty chunk strings.
    """
    chunk_size = chunk_size if chunk_size is not None else Config.CHUNK_SIZE
    overlap    = overlap    if overlap    is not None else Config.CHUNK_OVERLAP

    if not text or not text.strip():
        return []

    # If the whole text fits in one chunk, return it directly
    if len(text) <= chunk_size:
        stripped = text.strip()
        return [stripped] if len(stripped) >= _MIN_CHUNK_CHARS else []

    chunks: list[str] = []
    start   = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end >= text_len:
            # Final chunk — take whatever remains
            chunk = text[start:].strip()
            if len(chunk) >= _MIN_CHUNK_CHARS:
                chunks.append(chunk)
            break

        # ── Find the best split point ──────────────────────────────────

        split_at = end   # default: hard cut at chunk_size

        # 1. Paragraph boundary: look backwards from end to start + overlap
        para = text.rfind("\n\n", start + overlap, end)
        if para != -1:
            split_at = para
        else:
            # 2. Sentence boundary
            best_sent = -1
            for punct in (". ", "? ", "! ", ".\n", "?\n", "!\n"):
                pos = text.rfind(punct, start + overlap, end)
                if pos > best_sent:
                    best_sent = pos
            if best_sent != -1:
                split_at = best_sent + 1   # include the punctuation character
            else:
                # 3. Word boundary
                word = text.rfind(" ", start + overlap, end)
                if word != -1:
                    split_at = word
                # 4. Hard cut — split_at stays at end

        chunk = text[start:split_at].strip()
        if len(chunk) >= _MIN_CHUNK_CHARS:
            chunks.append(chunk)
        elif chunk and chunks:
            # Tiny fragment: append to previous chunk rather than discard
            chunks[-1] = chunks[-1] + " " + chunk

        # Advance with overlap — guard against infinite loop if split_at
        # did not advance past (start + overlap) (e.g., no whitespace/punct).
        new_start = split_at - overlap
        if new_start <= start:
            new_start = split_at   # force a hard advance; never go backwards
        start = new_start

    log.debug("Chunking complete: %d chunks from %d characters", len(chunks), text_len)
    return chunks


def get_page_number_for_chunk(
    chunk_start_char: int,
    page_map: list[tuple[int, int]],
) -> int:
    """
    Given the character offset where a chunk starts and the page_map
    [(char_offset, page_num), ...], return the page number that contains
    the start of the chunk.

    Falls back to page 1 if the map is empty.
    """
    if not page_map:
        return 1
    page_num = 1
    for char_offset, pnum in page_map:
        if chunk_start_char >= char_offset:
            page_num = pnum
        else:
            break
    return page_num


# ══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════════

def _build_word_page_map(paragraphs: list[str]) -> list[tuple[int, int]]:
    """
    Build a page_map for DOCX by tracking cumulative word count.
    Every ~300 words = one estimated page.
    """
    page_map: list[tuple[int, int]] = [(0, 1)]
    word_count = 0
    char_pos   = 0
    current_page = 1
    words_per_page = 300

    for para in paragraphs:
        word_count += len(para.split())
        char_pos   += len(para) + 1   # +1 for the "\n" join
        new_page    = (word_count // words_per_page) + 1
        if new_page > current_page:
            page_map.append((char_pos, new_page))
            current_page = new_page

    return page_map
