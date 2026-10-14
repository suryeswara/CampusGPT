import re
from collections import Counter
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend import config, retrieval
from backend.vectorstore import get_vectorstore


def safe_name(filename: str) -> str:
    """Strip any path and replace unsafe characters."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)


def add_pdf(path: Path) -> int:
    """Index one PDF (replacing an older version of the same name). Returns chunk count."""
    pages = PyPDFLoader(str(path)).load()
    for p in pages:
        p.metadata["source"] = path.name
        p.metadata["page"] = p.metadata.get("page", 0) + 1  # 1-based

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE, chunk_overlap=config.CHUNK_OVERLAP
    )
    chunks = [c for c in splitter.split_documents(pages) if c.page_content.strip()]
    if not chunks:
        raise ValueError("No extractable text found (scanned PDF?).")

    for i, c in enumerate(chunks):
        c.metadata["chunk_id"] = f"{path.name}:{c.metadata['page']}:{i}"

    vs = get_vectorstore()
    vs.delete(where={"source": path.name})  # replace old version, if any
    vs.add_documents(chunks, ids=[c.metadata["chunk_id"] for c in chunks])
    retrieval.rebuild_bm25()
    return len(chunks)


def delete_pdf(name: str) -> None:
    get_vectorstore().delete(where={"source": name})
    p = config.PDF_DIR / name
    if p.exists():
        p.unlink()
    retrieval.rebuild_bm25()


def list_docs() -> list[dict]:
    metas = get_vectorstore().get(include=["metadatas"]).get("metadatas") or []
    counts = Counter(m["source"] for m in metas)
    return [{"name": n, "chunks": c} for n, c in sorted(counts.items())]


def sync_folder() -> None:
    """Index PDFs found in data/pdfs that are not indexed yet (used at startup)."""
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    indexed = {d["name"] for d in list_docs()}
    for pdf in sorted(config.PDF_DIR.glob("*.pdf")):
        if pdf.name not in indexed:
            try:
                n = add_pdf(pdf)
                print(f"Indexed {pdf.name}: {n} chunks")
            except ValueError as e:
                print(f"Skipped {pdf.name}: {e}")


if __name__ == "__main__":
    sync_folder()
