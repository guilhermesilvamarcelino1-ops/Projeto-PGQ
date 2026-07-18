"""Text extraction + chunking for procedimento documents (PDF, DOCX, plain text)."""

import io
import re
from dataclasses import dataclass

from docx import Document as DocxDocument
from pypdf import PdfReader

MAX_CHUNK_CHARS = 1200
MIN_CHUNK_CHARS = 200


@dataclass
class RawChunk:
    content: str
    page_ref: int | None = None
    section_ref: str | None = None


def _split_paragraphs(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) > max_chars and buffer:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = candidate
    if buffer:
        chunks.append(buffer)
    # merge chunks that ended up too small into neighbours
    merged: list[str] = []
    for chunk in chunks:
        if merged and len(merged[-1]) < MIN_CHUNK_CHARS:
            merged[-1] = f"{merged[-1]}\n\n{chunk}"
        else:
            merged.append(chunk)
    return merged


def extract_pdf(file_bytes: bytes) -> list[RawChunk]:
    reader = PdfReader(io.BytesIO(file_bytes))
    chunks: list[RawChunk] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for piece in _split_paragraphs(text):
            chunks.append(RawChunk(content=piece, page_ref=page_num))
    return chunks


_HEADING_RE = re.compile(r"^\s*(\d+(\.\d+)*)[\.\)]?\s+\S")


def extract_docx(file_bytes: bytes) -> list[RawChunk]:
    doc = DocxDocument(io.BytesIO(file_bytes))
    chunks: list[RawChunk] = []
    current_section: str | None = None
    buffer_paras: list[str] = []

    def flush():
        if not buffer_paras:
            return
        text = "\n\n".join(buffer_paras)
        for piece in _split_paragraphs(text):
            chunks.append(RawChunk(content=piece, section_ref=current_section))
        buffer_paras.clear()

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        is_heading = para.style is not None and para.style.name.lower().startswith("heading")
        matches_numbered_section = bool(_HEADING_RE.match(text)) and len(text) < 120
        if is_heading or matches_numbered_section:
            flush()
            current_section = text
            continue
        buffer_paras.append(text)
    flush()
    return chunks


def extract_plain_text(text: str) -> list[RawChunk]:
    return [RawChunk(content=piece) for piece in _split_paragraphs(text)]


def extract_chunks(file_bytes: bytes | None, plain_text: str | None, content_type: str) -> list[RawChunk]:
    if plain_text is not None:
        return extract_plain_text(plain_text)
    if content_type == "application/pdf":
        return extract_pdf(file_bytes)
    if content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return extract_docx(file_bytes)
    raise ValueError(f"Tipo de arquivo não suportado: {content_type}")
