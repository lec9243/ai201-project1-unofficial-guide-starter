"""
retrieve.py — Query the ChromaDB index and return the top-k most relevant chunks.

Usage (as a module):
    from src.retrieve import retrieve
    results = retrieve("Who is good for CSCI2021?", k=4)

Usage (CLI test):
    python src/retrieve.py
"""

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Config — must match build_index.py
# ---------------------------------------------------------------------------

CHROMA_DIR  = Path("chroma_db")
COLLECTION  = "unofficial_guide"
EMBED_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Module-level singletons
# Loaded once when the module is first imported, reused on every query.
# ---------------------------------------------------------------------------

print("Loading embedding model ...")
_model = SentenceTransformer(EMBED_MODEL)

print(f"Connecting to ChromaDB at '{CHROMA_DIR}' ...")
_client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_collection(COLLECTION)
print(f"  Collection '{COLLECTION}' ready ({_collection.count()} chunks).\n")


# ---------------------------------------------------------------------------
# Retrieve function
# ---------------------------------------------------------------------------

def retrieve(query: str, k: int = 4, max_distance: float = None) -> list[dict]:
    """
    Embed query and return the top-k closest chunks from ChromaDB.

    Each result dict has:
        text      — the chunk text
        metadata  — source_file, professor, course, etc.
        distance  — cosine distance (lower = more similar; 0.0 is identical)

    Optional: pass max_distance (e.g. 0.6) to drop any result whose distance
    exceeds that threshold.  Useful in generation to avoid feeding weak matches
    to the language model.
    """
    # Embed the query with the same model used at index time
    query_embedding = _model.encode(query).tolist()

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    # results["documents"][0] is a list of k texts (the [0] unwraps the batch dimension)
    hits = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Skip this result if it exceeds the caller's distance threshold
        if max_distance is not None and dist > max_distance:
            continue
        hits.append({
            "text":     text,
            "metadata": meta,
            "distance": dist,
        })

    return hits


# ---------------------------------------------------------------------------
# CLI test block
# ---------------------------------------------------------------------------

TEST_QUERIES = [
    "Why do students recommend Kauffman for CSCI2021?",
    "How does the final work in Sebastiaan Joosten's CSCI2011?",
    "For CSCI2041, what do students say about choosing Moen versus Van Wyk in terms of workload, useful assignments, and learning?",
]

def print_results(query: str, hits: list[dict]) -> None:
    print(f"\n{'='*70}")
    print(f"QUERY: {query}")
    print(f"{'='*70}")
    for rank, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        # Collapse whitespace so the preview reads cleanly as a single line
        raw_preview = " ".join(hit["text"].split())
        preview = raw_preview[:300]
        print(f"\n  Rank {rank}  |  distance: {hit['distance']:.4f}")
        print(f"  source_file : {meta['source_file']}")
        print(f"  professor   : {meta['professor']}")
        print(f"  course      : {meta['course']}")
        print(f"  preview     : {preview}...")


if __name__ == "__main__":
    for q in TEST_QUERIES:
        hits = retrieve(q, k=4)
        print_results(q, hits)
    print(f"\n{'='*65}")
