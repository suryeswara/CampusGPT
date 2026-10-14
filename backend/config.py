import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "pdfs"
DB_DIR = str(ROOT / "chroma_db")
SQLITE_PATH = str(ROOT / "campusgpt.db")
COLLECTION = "campusgpt"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Chunk size is in characters, not tokens.
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))

FETCH_K = int(os.getenv("FETCH_K", 20))        # candidates per search method
FINAL_K = int(os.getenv("FINAL_K", 4))         # chunks sent to the LLM
RRF_K = 60                                     # standard RRF constant

# Gate 1: best vector cosine distance must be below this (lower = more similar).
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", 0.8))
# Gate 2: reranker score must be above this (raw logit, higher = more relevant).
MIN_RERANK_SCORE = float(os.getenv("MIN_RERANK_SCORE", -4))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v3")

HISTORY_TURNS = 6                              # messages used for rewriting
NOT_FOUND = "Not found in the documents."

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 20))
UPLOAD_ENABLED = os.getenv("UPLOAD_ENABLED", "true").lower() == "true"
