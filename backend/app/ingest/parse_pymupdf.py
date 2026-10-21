"""Parse a raw PDF into word boxes and structure-aware chunks.

Chunks are built from the words themselves, so every chunk maps back to exact
word indices, and through them to rectangles on the original PDF page.
"""
from dataclasses import dataclass, field
from statistics import median

import fitz  # PyMuPDF

MAX_CHUNK_WORDS = 220


@dataclass
class Word:
    idx: int
    page: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block: tuple[int, int]  # (page, block_no)


@dataclass
class Chunk:
    ord: int
    section_path: str
    word_start: int
    word_end: int
    page_start: int
    page_end: int
    text: str = ""


@dataclass
class ParsedDoc:
    page_count: int
    words: list[Word]
    chunks: list[Chunk] = field(default_factory=list)


def parse_pdf(data: bytes) -> ParsedDoc:
    doc = fitz.open(stream=data, filetype="pdf")
    words: list[Word] = []
    for pno, page in enumerate(doc):
        # (x0, y0, x1, y1, text, block_no, line_no, word_no), sorted into reading order
        for x0, y0, x1, y1, text, b, _l, _w in page.get_text("words", sort=True):
            words.append(Word(len(words), pno, text, x0, y0, x1, y1, (pno, b)))
    parsed = ParsedDoc(page_count=doc.page_count, words=words)
    parsed.chunks = _chunk(words)
    return parsed


def _chunk(words: list[Word]) -> list[Chunk]:
    """Group words by PDF block; start a new chunk at headings (taller text) or size limit."""
    if not words:
        return []
    blocks: list[list[Word]] = []
    for w in words:
        if blocks and blocks[-1][0].block == w.block:
            blocks[-1].append(w)
        else:
            blocks.append([w])

    body_h = median(w.y1 - w.y0 for w in words)
    is_heading = lambda blk: median(w.y1 - w.y0 for w in blk) > body_h * 1.15  # noqa: E731

    chunks: list[Chunk] = []
    section = ""
    cur: list[Word] = []

    def flush():
        if cur:
            chunks.append(Chunk(len(chunks), section, cur[0].idx, cur[-1].idx, cur[0].page, cur[-1].page,
                                " ".join(w.text for w in cur)))
            cur.clear()

    for blk in blocks:
        if is_heading(blk):
            flush()
            section = " ".join(w.text for w in blk)
        elif len(cur) + len(blk) > MAX_CHUNK_WORDS:
            flush()
        cur.extend(blk)
    flush()
    return chunks
