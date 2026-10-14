import json
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import config, ingest, rag, retrieval, store

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init()
    ingest.sync_folder()        # index any PDFs already on disk
    retrieval.rebuild_bm25()
    yield


app = FastAPI(title="CampusGPT", lifespan=lifespan)


# ---------- request models ----------

class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Msg] = Field(default_factory=list, max_length=20)
    sources: list[str] | None = None
    mode: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank"


class FeedbackRequest(BaseModel):
    question: str = Field(max_length=1000)
    answer: str = Field(max_length=8000)
    rating: Literal[-1, 1]
    mode: str = Field(max_length=30)


# ---------- routes ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/docs")
def docs():
    return ingest.list_docs()


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    if not config.UPLOAD_ENABLED:
        raise HTTPException(403, "Uploads are disabled on this server.")
    name = ingest.safe_name(file.filename or "")
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed.")

    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "This does not look like a valid PDF.")

    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PDF_DIR / name
    path.write_bytes(data)
    try:
        chunks = ingest.add_pdf(path)
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    return {"name": name, "chunks": chunks}


@app.delete("/api/docs/{name}")
def delete_doc(name: str):
    if not config.UPLOAD_ENABLED:
        raise HTTPException(403, "Deleting is disabled on this server.")
    if name != ingest.safe_name(name):
        raise HTTPException(400, "Invalid file name.")
    ingest.delete_pdf(name)
    return {"deleted": name}


@app.post("/api/chat")
def chat(req: ChatRequest):
    history = [m.model_dump() for m in req.history]

    def event_stream():
        for event, data in rag.stream_answer(
            req.question, history, req.sources, req.mode
        ):
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    store.add_feedback(req.question, req.answer, req.rating, req.mode)
    return {"ok": True}


# Serve the front end. Mounted last so /api routes take priority.
app.mount("/", StaticFiles(directory=config.ROOT / "frontend", html=True), name="frontend")
