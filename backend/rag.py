import logging
import time
from functools import lru_cache

from langchain_core.output_parsers import StrOutputParser

from backend import config, retrieval, store
from backend.prompts import get_answer_prompt, get_rewrite_prompt

log = logging.getLogger("campusgpt")


@lru_cache(maxsize=1)
def get_llm():
    if config.LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=config.LLM_MODEL, temperature=0)
    from langchain_groq import ChatGroq
    return ChatGroq(model=config.LLM_MODEL, temperature=0, groq_api_key=config.GROQ_API_KEY)


def rewrite_query(question: str, history: list[dict]) -> str:
    """Turn a follow-up like 'what about hostel students?' into a standalone query."""
    if not history:
        return question
    convo = "\n".join(
        f"{m['role']}: {m['content']}" for m in history[-config.HISTORY_TURNS:]
    )
    try:
        chain = get_rewrite_prompt() | get_llm() | StrOutputParser()
        rewritten = chain.invoke({"history": convo, "question": question}).strip()
        return rewritten or question
    except Exception:
        log.exception("Query rewrite failed; using the original question")
        return question


def format_context(hits) -> str:
    blocks = []
    for i, h in enumerate(hits, start=1):
        m = h.doc.metadata
        blocks.append(f"[{i}] ({m['source']}, p. {m['page']})\n{h.doc.page_content}")
    return "\n\n".join(blocks)


def serialize(hit) -> dict:
    m = hit.doc.metadata
    return {
        "source": m["source"],
        "page": m["page"],
        "score": round(hit.score, 3),
        "text": hit.doc.page_content,
    }


def stream_answer(question, history, sources, mode, log_query=True):
    """Yields (event, data): rewrite, sources, token, error, done."""
    t0 = time.time()
    standalone = rewrite_query(question, history)
    yield "rewrite", standalone

    hits = retrieval.retrieve(standalone, sources or None, mode)
    yield "sources", [serialize(h) for h in hits]

    if not hits:
        yield "token", config.NOT_FOUND
    else:
        try:
            chain = get_answer_prompt(config.PROMPT_VERSION) | get_llm() | StrOutputParser()
            for piece in chain.stream(
                {"context": format_context(hits), "question": standalone}
            ):
                yield "token", piece
        except Exception:
            log.exception("LLM call failed")
            yield "error", "The language model request failed. Check the API key and rate limits."

    latency = int((time.time() - t0) * 1000)
    if log_query:
        store.log_query(question, standalone, mode, len(hits), latency)
    yield "done", {"latency_ms": latency}
