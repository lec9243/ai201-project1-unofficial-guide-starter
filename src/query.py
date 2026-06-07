"""
query.py — Grounded generation for the Unofficial Guide RAG system.

The ask() function:
  1. Retrieves relevant chunks from ChromaDB using retrieve()
  2. Builds a prompt that gives the LLM only those chunks as context
  3. Calls the Groq API to generate an answer
  4. Returns the answer, source list, and raw chunks

Run from repo root:
    python src/query.py
"""

import os
from dotenv import load_dotenv
from groq import Groq

# retrieve() lives in src/retrieve.py.
# The try/except handles two run contexts:
#   - "python src/query.py"  from repo root  → `src` is a package, use "src.retrieve"
#   - "python query.py"      from inside src/ → use plain "retrieve"
try:
    from src.retrieve import retrieve
except ModuleNotFoundError:
    from retrieve import retrieve

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Load GROQ_API_KEY from .env file in the repo root
load_dotenv()

MODEL = "llama-3.3-70b-versatile"

# Distance threshold: chunks with cosine distance above this are too weak to use.
# 0.55 means "at least moderately related" — tune down to 0.45 to be stricter.
MAX_DISTANCE = 0.55

# How many chunks to retrieve before filtering by distance
TOP_K = 4

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(question: str, chunks: list[dict]) -> str:
    """
    Assemble the context block and instruction prompt sent to the LLM.

    Each chunk is numbered and includes its metadata so the model can see
    which document the information comes from.  The instructions tell the
    model to stay grounded and flag conflicts between student opinions.
    """
    # Build a numbered list of context chunks
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        context_parts.append(
            f"[{i}] Source: {meta['source_file']}\n"
            f"    Professor: {meta['professor']}\n"
            f"    Course: {meta['course']}\n"
            f"    URL: {meta['original_url']}\n"
            f"    Text: {chunk['text']}"
        )
    context_block = "\n\n".join(context_parts)

    prompt = f"""You are a helpful assistant that answers questions about University of Minnesota CS professors and courses.

You must follow these rules:
- Answer ONLY using the context documents provided below.
- Do NOT use any outside knowledge, even if you know about the topic.
- If the context does not contain enough information to answer the question, say: "I don't have enough information in the collected documents to answer that."
- If student opinions in the context conflict with each other, mention the disagreement rather than picking one side.
- Be specific: quote or closely paraphrase the relevant parts of the context.
- Keep your answer concise and focused on what the student asked.

CONTEXT DOCUMENTS:
{context_block}

QUESTION: {question}

ANSWER:"""

    return prompt


# ---------------------------------------------------------------------------
# Main ask() function
# ---------------------------------------------------------------------------

def ask(question: str) -> dict:
    """
    Full RAG pipeline: retrieve relevant chunks, then generate a grounded answer.

    Returns a dict with:
        answer           — the LLM's response string
        sources          — deduplicated list of source identifiers
        retrieved_chunks — the raw list of chunk dicts from retrieve()
    """
    # Step 1: Retrieve top chunks, filtered by distance threshold
    chunks = retrieve(question, k=TOP_K, max_distance=MAX_DISTANCE)

    # Step 2: If nothing came back above the threshold, refuse gracefully
    if not chunks:
        return {
            "answer": "I don't have enough information in the collected documents to answer that.",
            "sources": [],
            "retrieved_chunks": [],
        }

    # Step 3: Build the prompt with the retrieved context
    prompt = build_prompt(question, chunks)

    # Step 4: Call the Groq API
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,   # low temperature = more factual, less creative
    )
    answer_text = response.choices[0].message.content.strip()

    # Step 5: Build the sources list programmatically from retrieved chunks.
    # We do this in code (not relying on the LLM) so sources are always accurate.
    seen = set()
    sources = []
    for chunk in chunks:
        meta = chunk["metadata"]
        # Prefer the original URL; fall back to the source file name
        label = meta["original_url"] if meta["original_url"] else meta["source_file"]
        if label not in seen:
            seen.add(label)
            sources.append(label)

    return {
        "answer": answer_text,
        "sources": sources,
        "retrieved_chunks": chunks,
    }


# ---------------------------------------------------------------------------
# CLI test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_questions = [
        # Should work — covered by the corpus
        "Why do students recommend Kauffman for CSCI2021?",
        # Should refuse — completely out of scope
        "What is the best pizza place near campus?",
    ]

    for question in test_questions:
        print(f"\n{'='*65}")
        print(f"Q: {question}")
        print(f"{'='*65}")
        result = ask(question)
        print(f"\nAnswer:\n{result['answer']}")
        print(f"\nSources:")
        for s in result["sources"]:
            print(f"  - {s}")
        print(f"\nChunks used: {len(result['retrieved_chunks'])}")
        for c in result["retrieved_chunks"]:
            print(f"  [{c['distance']:.4f}] {c['metadata']['source_file']}")
