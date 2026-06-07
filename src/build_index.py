"""
build_index.py — Embed chunks and store them in a persistent ChromaDB collection.

Pipeline:
  1. Load chunks from data/processed/chunks.json
  2. Load the sentence-transformers embedding model
  3. Create (or reset) a ChromaDB collection
  4. Embed enriched text (metadata header + chunk text) for each chunk
  5. Persist the database to chroma_db/

Run from repo root:
    python src/build_index.py
"""

import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNKS_FILE   = Path("data/processed/chunks.json")
CHROMA_DIR    = Path("chroma_db")
COLLECTION    = "unofficial_guide"
EMBED_MODEL   = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Enriched text builder
# ---------------------------------------------------------------------------

def make_enriched_text(chunk: dict) -> str:
    """
    Prepend key metadata fields to the chunk text before embedding.

    Why: the embedding model only sees what it is given.  If a chunk's body
    says "he is the best professor" without repeating the professor name or
    course number, a query like "Who is good for CSCI2041?" has no textual
    anchor to match against.  Adding the metadata as a short header gives the
    model those anchors so the vector lands near relevant queries.

    The enriched text is only used for computing the embedding vector.
    The raw chunk text (without this header) is what gets stored and returned
    to the user, so answers stay clean.
    """
    header = (
        f"Title: {chunk['title']}\n"
        f"Source: {chunk['source']}\n"
        f"Professor: {chunk['professor']}\n"
        f"Course: {chunk['course']}\n"
        f"Document type: {chunk['document_type']}\n\n"
    )
    return header + chunk["text"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Step 1 — Load chunks
    print(f"Loading chunks from {CHUNKS_FILE} ...")
    with CHUNKS_FILE.open(encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"  {len(chunks)} chunks loaded.")

    # Step 2 — Load embedding model
    # all-MiniLM-L6-v2 is small, fast, and good at semantic similarity tasks.
    print(f"\nLoading embedding model '{EMBED_MODEL}' ...")
    model = SentenceTransformer(EMBED_MODEL)
    print("  Model ready.")

    # Step 3 — Set up a persistent ChromaDB client
    # PersistentClient saves the database to disk so retrieve.py can reuse it.
    print(f"\nConnecting to ChromaDB at '{CHROMA_DIR}' ...")
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Delete the collection if it already exists, then recreate it fresh.
    # This makes the script safe to re-run without duplicate entries.
    existing = [c.name for c in client.list_collections()]
    if COLLECTION in existing:
        client.delete_collection(COLLECTION)
        print(f"  Deleted existing collection '{COLLECTION}'.")

    collection = client.create_collection(
        name=COLLECTION,
        # cosine distance is standard for sentence-transformer embeddings
        metadata={"hnsw:space": "cosine"},
    )
    print(f"  Collection '{COLLECTION}' created.")

    # Step 4 — Embed and insert in one batch
    # ChromaDB accepts lists: ids, documents (text), embeddings, metadatas.
    print(f"\nEmbedding {len(chunks)} chunks ...")

    ids = [c["id"] for c in chunks]

    # Build enriched text: prepend metadata fields before the chunk body.
    # The embedding is computed from this enriched text so that queries
    # mentioning a course number or professor name land closer to the right
    # chunk in vector space.  The raw chunk text is still stored separately
    # in `documents` so retrieve.py can return the clean body to the user.
    documents  = [c["text"] for c in chunks]
    embed_texts = [make_enriched_text(c) for c in chunks]

    # Embed the enriched texts (SentenceTransformer handles batching internally)
    embeddings  = model.encode(embed_texts, show_progress_bar=True).tolist()

    # Build metadata dicts — ChromaDB requires all values to be str/int/float/bool
    metadatas = [
        {
            "source_file":   c["source_file"],
            "chunk_index":   c["chunk_index"],
            "title":         c["title"],
            "source":        c["source"],
            "original_url":  c["original_url"],
            "professor":     c["professor"],
            "course":        c["course"],
            "document_type": c["document_type"],
        }
        for c in chunks
    ]

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    # Step 5 — Confirm
    count = collection.count()
    print(f"\nIndexed {count} chunks into collection '{COLLECTION}'.")
    print(f"Database persisted to '{CHROMA_DIR}/'.")


if __name__ == "__main__":
    main()
