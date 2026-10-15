"""Deterministic, provenance-preserving chunking of extracted page text."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID, uuid5

CHUNK_NAMESPACE = UUID("48f602fb-cc2a-4de3-8e44-6f6a2dfab5b1")
CHUNKING_VERSION = "medical-pages-v1"
SECTION_RE = re.compile(r"(?im)^\s*((?:patient|specimen|test|laboratory|clinical|diagnosis|medication|result|impression|findings|history|reference)\s*(?:details?|information|results?|range)?\s*:?)\s*$")


@dataclass(frozen=True)
class Chunk:
    id: UUID
    index: int
    content: str
    content_hash: str
    page_number: int | None
    section: str | None


def _split_page(text: str, limit: int, overlap: int) -> list[tuple[str, str | None]]:
    text = re.sub(r"[ \t]+", " ", text.replace("\x00", "")).strip()
    if not text:
        return []
    # Keep explicit section headings with their following content.
    sections: list[tuple[str | None, str]] = []
    current_name: str | None = None
    current: list[str] = []
    for line in text.splitlines():
        match = SECTION_RE.match(line)
        if match and current:
            sections.append((current_name, "\n".join(current).strip()))
            current = []
        if match:
            current_name = match.group(1).strip(" :")[:100]
        current.append(line)
    if current:
        sections.append((current_name, "\n".join(current).strip()))

    output: list[tuple[str, str | None]] = []
    for name, section in sections:
        if len(section) <= limit:
            output.append((section, name))
            continue
        start = 0
        while start < len(section):
            end = min(len(section), start + limit)
            if end < len(section):
                # Prefer a paragraph or sentence boundary without splitting a short lab value/unit pair.
                boundary = max(section.rfind("\n", start, end), section.rfind(". ", start, end))
                if boundary > start + limit // 2:
                    end = boundary + (1 if section[boundary] == "\n" else 2)
            part = section[start:end].strip()
            if part:
                output.append((part, name))
            if end >= len(section):
                break
            start = max(start + 1, end - overlap)
            while start < len(section) and section[start].isspace():
                start += 1
    return output


def chunk_pages(document_id: UUID, generation: int, pages, *, max_chars: int = 1200, overlap: int = 160) -> list[Chunk]:
    """Chunk page records into stable IDs; never merges across page boundaries."""
    if max_chars <= 0 or overlap < 0 or overlap >= max_chars:
        raise ValueError("chunk size and overlap are invalid")
    chunks: list[Chunk] = []
    for page in pages:
        text = getattr(page, "extracted_text", None) or ""
        page_number = getattr(page, "page_number", None)
        for content, section in _split_page(text, max_chars, overlap):
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            index = len(chunks)
            stable = uuid5(CHUNK_NAMESPACE, f"{document_id}:{generation}:{index}:{digest}")
            chunks.append(Chunk(stable, index, content, digest, page_number, section))
    return chunks
