"""
app.py — Gradio web UI for the Unofficial Guide RAG system.

Displays three output panels:
  1. Answer        — the LLM's grounded response
  2. Sources       — URLs or filenames of retrieved documents
  3. Retrieved chunks — raw text and metadata for inspection

Run from repo root:
    python app.py
"""

import gradio as gr
from src.query import ask

# ---------------------------------------------------------------------------
# Wrapper that formats ask() output for the three Gradio output boxes
# ---------------------------------------------------------------------------

def answer_question(question: str):
    """
    Called by Gradio when the user submits a question.
    Returns three strings: answer, sources block, chunks block.
    """
    if not question.strip():
        return "Please enter a question.", "", ""

    result = ask(question)

    # --- Format sources ---
    if result["sources"]:
        sources_text = "\n".join(f"• {s}" for s in result["sources"])
    else:
        sources_text = "No sources retrieved."

    # --- Format retrieved chunks for the inspection panel ---
    chunks = result["retrieved_chunks"]
    if chunks:
        chunk_lines = []
        for i, chunk in enumerate(chunks, start=1):
            meta = chunk["metadata"]
            # Collapse whitespace in the preview so it reads as a single block
            preview = " ".join(chunk["text"].split())
            chunk_lines.append(
                f"Chunk {i}  |  distance: {chunk['distance']:.4f}\n"
                f"  File      : {meta['source_file']}\n"
                f"  Professor : {meta['professor']}\n"
                f"  Course    : {meta['course']}\n"
                f"  Text      : {preview}\n"
            )
        chunks_text = "\n".join(chunk_lines)
    else:
        chunks_text = "No chunks retrieved (question may be out of scope)."

    return result["answer"], sources_text, chunks_text


# ---------------------------------------------------------------------------
# Gradio UI layout
# ---------------------------------------------------------------------------

with gr.Blocks(title="The Unofficial Guide — UMN CS") as demo:

    gr.Markdown(
        """
        # The Unofficial Guide: UMN CS Professors & Courses
        Ask questions about UMN Computer Science professors and courses based on
        collected Rate My Professors reviews and Reddit threads.

        **Examples to try:**
        - Why do students recommend Kauffman for CSCI2021?
        - How does the final work in Sebastiaan Joosten's CSCI2011?
        - For CSCI2041, what do students say about Moen versus Van Wyk?
        - What does the review say about Maria Gini's CSCI4511W exams?
        """
    )

    # Input
    question_box = gr.Textbox(
        label="Your question",
        placeholder="e.g. Is Jack Kolb's CSCI5103 worth taking?",
        lines=2,
    )

    submit_btn = gr.Button("Ask", variant="primary")

    # Outputs
    answer_box = gr.Textbox(label="Answer", lines=8, interactive=False)

    sources_box = gr.Textbox(label="Sources", lines=4, interactive=False)

    chunks_box = gr.Textbox(
        label="Retrieved chunks (for inspection)",
        lines=12,
        interactive=False,
    )

    # Wire up the button and also allow Enter-to-submit via the textbox
    submit_btn.click(
        fn=answer_question,
        inputs=question_box,
        outputs=[answer_box, sources_box, chunks_box],
    )
    question_box.submit(
        fn=answer_question,
        inputs=question_box,
        outputs=[answer_box, sources_box, chunks_box],
    )

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # share=False keeps the app local; set share=True for a temporary public URL
    demo.launch(share=False)
