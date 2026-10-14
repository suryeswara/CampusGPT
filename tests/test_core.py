from langchain_core.documents import Document

from backend.ingest import safe_name
from backend.retrieval import rrf, tokenize


def doc(cid):
    return Document(page_content=cid, metadata={"chunk_id": cid})


def test_rrf_prefers_chunks_found_by_both_searches():
    vector = [(doc("1"), 0.1), (doc("2"), 0.2)]
    keyword = [(doc("2"), 9.0), (doc("3"), 8.0)]
    fused = rrf([vector, keyword])
    assert fused[0][0].metadata["chunk_id"] == "2"


def test_rrf_keeps_every_candidate_once():
    fused = rrf([[(doc("a"), 1)], [(doc("b"), 1)], [(doc("a"), 1)]])
    assert sorted(d.metadata["chunk_id"] for d, _ in fused) == ["a", "b"]


def test_tokenize_lowercases_and_splits():
    assert tokenize("Fee-Refund 2024!") == ["fee", "refund", "2024"]


def test_safe_name_strips_paths_and_bad_characters():
    assert safe_name("../../etc/pass wd.pdf") == "pass_wd.pdf"
