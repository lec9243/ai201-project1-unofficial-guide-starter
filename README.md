# The Unofficial Guide — Project 1

## Domain

This system covers student reviews of Computer Science professors and courses at the University of Minnesota. This knowledge is useful because official course catalogs usually describe only course topics and requirements, but they do not explain teaching style, workload, attendance expectations, exam difficulty, textbook usefulness, or professor-specific advice. That information is usually scattered across Rate My Professors reviews, Reddit threads, and informal student conversations, so a RAG system can make it easier to search and summarize.

---

## Document Sources

| #  | Source                                            | Type             | URL or file path                                 |
| -- | ------------------------------------------------- | ---------------- | ------------------------------------------------ |
| 1  | Rate My Professors — Jack Kolb                    | Professor review | data/raw/01_rmp_jack_kolb_csci5103.txt           |
| 2  | Rate My Professors — Daniel Kluver                | Professor review | data/raw/02_rmp_daniel_kluver_csci4131.txt       |
| 3  | Rate My Professors — Kevin Wendt                  | Professor review | data/raw/03_rmp_kevin_wendt_csci5801.txt         |
| 4  | Rate My Professors — Maria Gini                   | Professor review | data/raw/04_rmp_maria_gini_csci4511w.txt         |
| 5  | Rate My Professors — Adriana Picoral              | Professor review | data/raw/05_rmp_adriana_picoral_csci1913.txt     |
| 6  | Reddit — CSCI 2011 w/ Sebastiaan Joosten          | Reddit thread    | data/raw/06_reddit_joosten_csci2011.txt          |
| 7  | Reddit — CSCI 2021: Thoughts on Kauffman?         | Reddit thread    | data/raw/07_reddit_kauffman_csci2021.txt         |
| 8  | Reddit — Prof Recommendations for CSCI classes    | Reddit thread    | data/raw/08_reddit_prof_recommendations_csci.txt |
| 9  | Reddit — How bad is Timothy Wrenn for CSCI 3081W? | Reddit thread    | data/raw/09_reddit_timothy_wrenn_csci3081w.txt   |
| 10 | Reddit — CSCI 2041 Moen vs Van Wyk                | Reddit thread    | data/raw/10_reddit_csci2041_moen_vanwyk.txt      |

---

## Chunking Strategy

**Chunk size:** 600–800 characters, using paragraph or comment boundaries when possible.

**Overlap:** 80–100 characters for long paragraphs that need forced splitting.

**Why these choices fit your documents:**
The documents are mostly short Rate My Professors reviews and Reddit comments. A single review or comment often contains one complete student opinion about a professor, workload, grading, attendance, or textbook usefulness. I used paragraph/comment-aware chunking so those opinions usually stay together. For longer comments, I split around 600–800 characters with overlap so that professor names, course numbers, and the reason for the opinion are less likely to be separated.

Before chunking, the ingestion script loads local `.txt` files from `data/raw/`, parses metadata such as title, source, original URL, professor, course, and document type, removes extra whitespace and HTML-like artifacts, and writes structured chunks to `data/processed/chunks.json`.

**Final chunk count:** 18 chunks across 10 documents.

---

## Embedding Model

**Model used:** `sentence-transformers/all-MiniLM-L6-v2`

**Production tradeoff reflection:**
I chose `all-MiniLM-L6-v2` because it runs locally, is free, has low latency, and works well enough for a small student-review corpus. If I were deploying this system for real users and cost was not a constraint, I would consider a stronger API-based embedding model with better semantic accuracy on slang, informal student language, and longer documents. I would also weigh tradeoffs such as cost per query, latency, context length, multilingual support, and whether the system needs to run locally or can depend on an external API.

---

## Grounded Generation

**System prompt grounding instruction:**
The generation step uses retrieved chunks as the only context. The prompt tells the model:

```text
Answer ONLY using the context documents provided below.
Do NOT use any outside knowledge, even if you know about the topic.
If the context does not contain enough information to answer the question, say:
"I don't have enough information in the collected documents to answer that."
If student opinions in the context conflict with each other, mention the disagreement rather than picking one side.
```

The system also filters retrieved chunks using a maximum distance threshold of `0.55`. This prevents weakly related chunks from being passed into the LLM during generation.

**How source attribution is surfaced in the response:**
Source attribution is added programmatically. The `ask()` function returns both the generated answer and a deduplicated list of source URLs or source files from the retrieved chunks. The Gradio interface displays the answer, the source list, and the raw retrieved chunks with metadata so the user can inspect where the answer came from.

---

## Evaluation Report

| # | Question                                                                                                                      | Expected answer                                                                                                                                                                                                             | System response (summarized)                                                                                                                                                                                             | Retrieval quality | Response accuracy  |
| - | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------- | ------------------ |
| 1 | What does the review say are the main workload challenges in Jack Kolb’s CSCI5103?                                            | Labs and homework are the main time sinks. They are difficult and time-consuming but rewarding. The review also says the exams are not too difficult.                                                                       | The system said the main workload comes from labs and homework, described as difficult, time-consuming, and rewarding.                                                                                                   | Relevant          | Accurate           |
| 2 | Why does the Maria Gini review say students need to read the textbook for CSCI4511W?                                          | Students need to read because exams may include textbook material not directly taught in lecture. The expected answer also includes that practice exam answer keys are not provided and the project is fairly unguided.     | The system said students need to read the textbook because exams may include material from the book that is not directly taught in lecture.                                                                              | Relevant          | Partially accurate |
| 3 | How does the final work in Sebastiaan Joosten’s CSCI2011, according to the Reddit thread?                                     | The final works as a re-sit or do-over for midterms the student missed or wants to improve. It can count heavily if used to replace midterms, or count as 0% if the student is satisfied with their midterm grades.         | The system said the final works as a re-sit or do-over for missed or improved midterms, and may count as a large part of the grade or as little as 0%.                                                                   | Relevant          | Accurate           |
| 4 | Why do students recommend Kauffman for CSCI2021?                                                                              | Students describe Kauffman as one of the best CS/CSE professors, caring, motivating, responsive to feedback, and helpful. The engagement point system lets students exchange extra lab points for late project submissions. | The system said students recommend Kauffman because he is motivating, energetic, caring, responsive to feedback, and has an engagement point system that can help with late project submissions.                         | Relevant          | Accurate           |
| 5 | For CSCI2041, what do students say about choosing Moen versus Van Wyk in terms of workload, useful assignments, and learning? | Moen is described as easier and less stressful, while Van Wyk has a heavier workload but more useful assignments, more material, and better deeper learning.                                                                | The system said Moen has a lighter workload, while Van Wyk has weekly labs, in-class work, long homeworks, quizzes, more useful assignments, more material, and is better for students who want to challenge themselves. | Relevant          | Accurate           |

**Retrieval quality:** Relevant / Partially relevant / Off-target
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

**Question that failed:**
Original version of evaluation question #5: “For CSCI2041, who should a student choose if they want an easier semester versus deeper learning?”

**What the system returned:**
The retrieval step initially returned a broader professor recommendation thread and some unrelated chunks instead of consistently returning the dedicated CSCI2041 Moen vs Van Wyk thread.

**Root cause (tied to a specific pipeline stage):**
This was a retrieval-stage problem. The original query was too abstract and did not include strong anchor terms such as “Moen,” “Van Wyk,” “workload,” or “assignments.” The embedding model matched the general meaning of “CSCI2041 professor recommendation” but did not reliably find the more specific Moen vs Van Wyk comparison.

**What you would change to fix it:**
I revised the evaluation question to include the professor names and comparison dimensions: workload, useful assignments, and learning. I also embedded metadata such as title, professor, course, and document type along with the chunk text, so queries that mention professor names or course numbers are more likely to retrieve the correct source.

---

## Spec Reflection

**One way the spec helped you during implementation:**
The planning document helped keep the implementation organized by separating the project into ingestion, chunking, embedding, retrieval, generation, and interface stages. Because I had already chosen a chunk size, overlap, embedding model, top-k value, and evaluation questions, I could use the spec to guide each script instead of making decisions while coding. The architecture diagram also made it easier to prompt Claude for one pipeline stage at a time.

**One way your implementation diverged from the spec, and why:**
My implementation diverged slightly from the first version of the evaluation plan. The original CSCI2041 question was too abstract, and retrieval did not reliably return the Moen vs Van Wyk thread. I revised the question to include “Moen,” “Van Wyk,” “workload,” “useful assignments,” and “learning” because the project instructions require evaluation questions to be specific enough to judge whether the system is right or wrong.

---

## AI Usage

**Instance 1**

* *What I gave the AI:* I gave Claude my Documents section, Chunking Strategy section, and Architecture diagram from `planning.md`. I asked it to implement an ingestion script that loads local `.txt` files, parses metadata, cleans text, and chunks according to my 600–800 character strategy with 80–100 character overlap.
* *What it produced:* Claude produced `src/ingest.py`, including functions for loading documents, parsing metadata, cleaning text, splitting paragraphs, force-splitting long text, building chunk dictionaries, and writing `data/processed/chunks.json`.
* *What I changed or overrode:* I inspected the output chunks and noticed some chunks started in the middle of words. I directed Claude to improve the splitting logic so chunks start and end more cleanly near whitespace or sentence boundaries. I also verified that metadata such as professor, course, source file, and original URL was preserved.

**Instance 2**

* *What I gave the AI:* I gave Claude my Retrieval Approach section and explained that I wanted `sentence-transformers/all-MiniLM-L6-v2`, ChromaDB, top-k retrieval, and source metadata.
* *What it produced:* Claude produced `src/build_index.py` and `src/retrieve.py`, which embed chunks, store them in ChromaDB, and retrieve top chunks with distance scores.
* *What I changed or overrode:* Initial retrieval did not reliably find the CSCI2041 Moen vs Van Wyk source for an abstract query. I changed the evaluation question to be more specific and directed Claude to include metadata such as title, professor, course, and document type in the embedded document text. I also added distance filtering so weakly related chunks are not passed to generation.

**Instance 3**

* *What I gave the AI:* I gave Claude my completed retrieval pipeline and asked it to implement grounded generation and a Gradio interface.
* *What it produced:* Claude produced `src/query.py` with a Groq-based `ask()` function and `app.py` with a Gradio UI showing answer, sources, and retrieved chunks.
* *What I changed or overrode:* I checked that the prompt explicitly prevented outside knowledge and required refusal when the retrieved context was insufficient. I also verified that sources were appended programmatically rather than relying only on the LLM to cite them.
