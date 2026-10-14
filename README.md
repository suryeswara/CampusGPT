# CampusGPT

> A document understanding assistant AI

Cited Q&A over college documents: hybrid retrieval, reranking and streaming answers.

**Live demo:** _(add link after deployment)_

## Features
- FastAPI backend with streaming (SSE) and a vanilla JavaScript front end
- Hybrid search (BM25 + vectors, Reciprocal Rank Fusion) and cross-encoder reranking
- Conversational follow-ups through LLM query rewriting
- Numbered citations that open the exact source chunk
- PDF upload, delete and per-document filtering
- Relevance gates that return "Not found" for out-of-scope questions
- Feedback and latency logging in SQLite
- Evaluation with Hit@k and MRR; unit tests; Docker

## Architecture

```
┌────────────────────── Browser (vanilla JS) ──────────────────────┐
│  index.html + style.css + app.js                                 │
│  chat UI · document sidebar · mode select · citations · feedback │
└───────────────┬──────────────────────────────────────────────────┘
                │ fetch (JSON, multipart, SSE stream)
┌───────────────▼──────────────── FastAPI ─────────────────────────┐
│ /api/chat  /api/docs  /api/upload  /api/feedback  static files   │
└───────┬───────────────────────────────────────────────┬──────────┘
        │                                               │
   rag.py                                          ingest.py
   1. rewrite follow-up question (LLM)             PDF → chunks
   2. retrieval.py                                 → embeddings → Chroma
        ├─ vector search (Chroma)                  → rebuild BM25 index
        ├─ BM25 keyword search
        ├─ Reciprocal Rank Fusion
        └─ cross-encoder rerank + thresholds
   3. prompt + context → LLM (streamed)
   4. log query to SQLite
```

## Results

| Mode | Hit@4 | MRR | Correct refusals |
|---|---|---|---|
| Vector | x/20 | x | x/5 |
| Hybrid | x/20 | x | x/5 |
| Hybrid + rerank | x/20 | x | x/5 |

_(Fill in from `eval/results.csv` after running evaluations)_

## Setup

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd campusgpt

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env          # Linux/Mac: cp .env.example .env
# Edit .env with your GROQ_API_KEY (or set LLM_PROVIDER=ollama)

# 5. Add PDFs to data/pdfs/

# 6. Run the server
uvicorn backend.main:app --reload

# 7. Open http://localhost:8000
```

### Running with Docker

```bash
docker build -t campusgpt .
docker run -p 8000:8000 --env-file .env campusgpt
```

### Evaluation

```bash
python -m backend.evaluate                          # retrieval only: fast and free
python -m backend.evaluate --answers hybrid_rerank  # also checks LLM answers
```

### Tests

```bash
pytest -q
```

## Design decisions
- **RRF over raw score addition:** Different search methods have incompatible score scales; ranks are universal.
- **Two relevance gates:** `MAX_DISTANCE` catches completely off-topic queries early; `MIN_RERANK_SCORE` filters irrelevant chunks after reranking.
- **Vanilla JS with `textContent` only:** Eliminates XSS risk from model output; no build step needed.

## Limitations
- Text-based PDFs only (no OCR)
- Keyword-based answer check is approximate
- Ephemeral storage on free hosting tiers

## Future work
- Authentication and per-user document collections
- OCR for scanned PDFs (Tesseract)
- LLM-as-judge faithfulness evaluation
- Replace Chroma with Qdrant or pgvector
>>>>>>> 0cc5c97 (Initial commit: CampusGPT repository)
