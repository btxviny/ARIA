"""Parsing + chunking for uploaded personal sources (PDF / TXT / Markdown)."""
import io
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from src.config import RAG_CHUNK_OVERLAP, RAG_CHUNK_SIZE

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


class UnsupportedFileType(ValueError):
    """Raised when an uploaded file's extension isn't one we can parse."""


def _load_pages(raw_bytes: bytes, filename: str) -> List[Document]:
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(Document(page_content=text, metadata={"page": i + 1}))
        if not pages:
            raise ValueError(f"No extractable text found in PDF '{filename}'.")
        return pages

    if suffix in (".txt", ".md"):
        text = raw_bytes.decode("utf-8", errors="replace").strip()
        if not text:
            raise ValueError(f"File '{filename}' is empty.")
        return [Document(page_content=text, metadata={})]

    raise UnsupportedFileType(
        f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def load_and_chunk(raw_bytes: bytes, filename: str, source_id: str) -> List[Document]:
    """Parse an uploaded file into page-level Documents, then split into chunks.

    Each returned chunk's metadata carries `filename`, `source_id`, and
    `chunk_index` (0-based, ordinal within this file), plus `page` for PDFs.
    """
    pages = _load_pages(raw_bytes, filename)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=RAG_CHUNK_SIZE,
        chunk_overlap=RAG_CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)
    if not chunks:
        raise ValueError(f"No chunkable content found in '{filename}'.")

    for i, chunk in enumerate(chunks):
        chunk.metadata["filename"] = filename
        chunk.metadata["source_id"] = source_id
        chunk.metadata["chunk_index"] = i
    return chunks
