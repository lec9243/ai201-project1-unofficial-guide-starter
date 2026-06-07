"""
ingest.py — Document ingestion pipeline for the Unofficial Guide RAG system.

Pipeline stages:
  1. Load: read every .txt file from data/raw/
  2. Parse: split metadata header from body text
  3. Clean: normalize whitespace, strip empty lines, remove HTML tags
  4. Chunk: split on paragraph/comment boundaries, targeting 600–800 chars
  5. Write: output all chunks to data/processed/chunks.json

Run from repo root:
    python src/ingest.py
"""

import json
import os
import re
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/processed/chunks.json")

# ---------------------------------------------------------------------------
# Chunking parameters (characters, not tokens)
# ---------------------------------------------------------------------------

CHUNK_TARGET = 700      # aim for the middle of the 600–800 range
CHUNK_MAX = 800         # hard ceiling before we force a split
OVERLAP = 100           # characters carried forward when force-splitting
MIN_CHUNK = 80          # discard fragments shorter than this


# ---------------------------------------------------------------------------
# Step 1 — Load raw text files
# ---------------------------------------------------------------------------

def load_documents(raw_dir: Path) -> list[dict]:
    """Read every .txt file in raw_dir and return a list of raw document dicts."""
    docs = []
    for path in sorted(raw_dir.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        docs.append({"source_file": path.name, "raw_text": text})
    return docs


# ---------------------------------------------------------------------------
# Step 2 — Parse metadata header
# ---------------------------------------------------------------------------

# Metadata fields we recognise in the header block.
# Both singular and plural forms map to the same output key.
FIELD_MAP = {
    "title":          "title",
    "source":         "source",
    "original url":   "original_url",
    "professor":      "professor",
    "professors":     "professor",      # normalised to one key
    "professor(s)":   "professor",      # raw files use this form
    "course":         "course",
    "courses":        "course",         # normalised to one key
    "course(s)":      "course",         # raw files use this form
    "document type":  "document_type",
    # Fields we intentionally skip (date, processing note)
}

def parse_metadata(raw_text: str) -> tuple[dict, str]:
    """
    Split the file into a metadata dict and the body text.

    The header is every line before the first blank line.
    Each header line has the form  "Field: value".
    The body begins after the "Cleaned corpus note:" marker (or after the
    header if that marker is absent).
    Returns (metadata_dict, body_text).
    """
    meta = {
        "title": "",
        "source": "",
        "original_url": "",
        "professor": "",
        "course": "",
        "document_type": "",
    }

    lines = raw_text.splitlines()

    # Collect header lines (everything before the first blank line)
    header_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            body_start = i + 1
            break
        header_lines.append(line)
    else:
        body_start = len(lines)

    for line in header_lines:
        if ":" in line:
            key_raw, _, value = line.partition(":")
            key = key_raw.strip().lower()
            value = value.strip()
            if key in FIELD_MAP:
                meta[FIELD_MAP[key]] = value

    # The body is everything after the header.
    # Strip the "Cleaned corpus note:" label and "Useful retrieval topics:" section.
    body_lines = lines[body_start:]
    body_text = "\n".join(body_lines)

    # Remove the "Cleaned corpus note:" label itself (keep the text beneath it)
    body_text = re.sub(r"(?i)^cleaned corpus note:\s*", "", body_text.strip())

    # Drop the "Useful retrieval topics:" section and everything after it
    body_text = re.split(r"(?i)\buseful retrieval topics\b", body_text)[0]

    # Also remove "Processing note:" lines if they slipped into the body
    body_text = re.sub(r"(?i)processing note:.*", "", body_text)

    return meta, body_text.strip()


# ---------------------------------------------------------------------------
# Step 3 — Clean body text
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Normalize whitespace, strip HTML tags, and remove blank lines.
    Preserves paragraph boundaries as single blank lines so the chunker
    can use them as split points.
    """
    # Remove HTML tags (e.g. <b>, </p>, &nbsp;)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)

    # Collapse multiple spaces / tabs on a single line
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        lines.append(line)

    # Collapse runs of 3+ blank lines into a single blank line (paragraph break)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


# ---------------------------------------------------------------------------
# Step 4 — Chunk text
# ---------------------------------------------------------------------------

def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on blank lines."""
    paragraphs = re.split(r"\n\n+", text)
    return [p.strip() for p in paragraphs if p.strip()]


def force_split(paragraph: str, max_size: int, overlap: int) -> list[str]:
    """
    Break a single long paragraph into pieces of at most max_size characters.
    Each piece (after the first) starts overlap characters before the previous
    piece ended, so context isn't lost mid-sentence.
    """
    pieces = []
    start = 0
    while start < len(paragraph):
        end = start + max_size
        piece = paragraph[start:end]
        pieces.append(piece)
        # Advance by (max_size - overlap) so the next chunk recaps the tail
        start += max_size - overlap
    return pieces


def chunk_document(body: str) -> list[str]:
    """
    Convert cleaned body text into a list of chunk strings.

    Strategy:
      - Split on paragraph boundaries first.
      - Greedily merge consecutive short paragraphs until we hit CHUNK_MAX.
      - If a single paragraph exceeds CHUNK_MAX, force-split with overlap.
      - Discard any resulting fragment shorter than MIN_CHUNK (unless it's
        the only chunk — i.e. the whole document is short).
    """
    paragraphs = split_paragraphs(body)

    if not paragraphs:
        return []

    # If the entire document is short, return as one chunk
    full_text = " ".join(paragraphs)
    if len(full_text) <= CHUNK_MAX:
        return [full_text]

    # Greedy merging pass
    raw_chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        # A single paragraph that is already too long — force-split it first
        if len(para) > CHUNK_MAX:
            # Flush whatever is in the buffer first
            if buffer:
                raw_chunks.append(buffer.strip())
                buffer = ""
            raw_chunks.extend(force_split(para, CHUNK_MAX, OVERLAP))
            continue

        candidate = (buffer + "\n\n" + para).strip() if buffer else para

        if len(candidate) <= CHUNK_MAX:
            # Still fits — keep accumulating
            buffer = candidate
        else:
            # Adding this paragraph would overflow — flush and start fresh
            if buffer:
                raw_chunks.append(buffer.strip())
            buffer = para

    # Flush any remaining buffer
    if buffer:
        raw_chunks.append(buffer.strip())

    # Filter out fragments that are too short (but keep if it's the only one)
    if len(raw_chunks) == 1:
        return raw_chunks

    return [c for c in raw_chunks if len(c) >= MIN_CHUNK]


# ---------------------------------------------------------------------------
# Step 5 — Build chunk records
# ---------------------------------------------------------------------------

def make_chunk_id(source_file: str, chunk_index: int) -> str:
    """
    Derive a human-readable chunk ID from the source filename.
    Example: "01_rmp_jack_kolb_csci5103.txt" + 0  ->  "01_rmp_jack_kolb_csci5103_chunk_0"
    """
    stem = Path(source_file).stem   # remove .txt
    return f"{stem}_chunk_{chunk_index}"


def build_chunks(doc: dict) -> list[dict]:
    """Full pipeline for one document: parse -> clean -> chunk -> annotate."""
    meta, body = parse_metadata(doc["raw_text"])
    cleaned_body = clean_text(body)
    texts = chunk_document(cleaned_body)

    chunks = []
    for i, text in enumerate(texts):
        chunks.append({
            "id":           make_chunk_id(doc["source_file"], i),
            "text":         text,
            "source_file":  doc["source_file"],
            "chunk_index":  i,
            "title":        meta["title"],
            "source":       meta["source"],
            "original_url": meta["original_url"],
            "professor":    meta["professor"],
            "course":       meta["course"],
            "document_type": meta["document_type"],
        })
    return chunks


# ---------------------------------------------------------------------------
# Step 6 — Write output
# ---------------------------------------------------------------------------

def write_chunks(chunks: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Step 7 — Summary report
# ---------------------------------------------------------------------------

def print_summary(docs: list[dict], chunks: list[dict]) -> None:
    print(f"\n{'='*60}")
    print(f"Documents loaded : {len(docs)}")
    print(f"Total chunks     : {len(chunks)}")

    # Chunks per source file
    print(f"\nChunks per source file:")
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c["source_file"]] = counts.get(c["source_file"], 0) + 1
    for fname, n in sorted(counts.items()):
        print(f"  {fname}: {n} chunk(s)")

    # 5 sample chunks
    print(f"\n{'-'*60}")
    print("5 sample chunks:")
    for chunk in chunks[:5]:
        preview = chunk["text"][:120].replace("\n", " ")
        print(f"\n  id           : {chunk['id']}")
        print(f"  professor    : {chunk['professor']}")
        print(f"  course       : {chunk['course']}")
        print(f"  document_type: {chunk['document_type']}")
        print(f"  text preview : {preview}...")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Loading documents from {RAW_DIR} ...")
    docs = load_documents(RAW_DIR)
    if not docs:
        print("No .txt files found in data/raw/. Exiting.")
        return

    all_chunks: list[dict] = []
    for doc in docs:
        chunks = build_chunks(doc)
        all_chunks.extend(chunks)

    write_chunks(all_chunks, OUTPUT_FILE)
    print(f"Wrote {len(all_chunks)} chunks to {OUTPUT_FILE}")

    print_summary(docs, all_chunks)


if __name__ == "__main__":
    main()
