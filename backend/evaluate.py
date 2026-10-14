import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

from backend import config, rag, retrieval

MODES = ["vector", "hybrid", "hybrid_rerank"]


def is_hit(hit, item) -> bool:
    m = hit.doc.metadata
    same_source = not item.get("source") or m["source"] == item["source"]
    return same_source and m["page"] == item["page"]


def collect_answer(question: str, mode: str) -> str:
    text = ""
    for event, data in rag.stream_answer(question, [], None, mode, log_query=False):
        if event == "token":
            text += data
    return text


def run(answers_mode: str | None):
    items = json.loads(Path("eval/questions.json").read_text())
    answerable = [i for i in items if i["answerable"]]
    unanswerable = [i for i in items if not i["answerable"]]
    rows = []

    for mode in MODES:
        hits_at_k, rr_sum = 0, 0.0
        for it in answerable:
            results = retrieval.retrieve(it["question"], None, mode)
            for rank, h in enumerate(results, start=1):
                if is_hit(h, it):
                    hits_at_k += 1
                    rr_sum += 1 / rank
                    break

        refused = sum(1 for it in unanswerable if not retrieval.retrieve(it["question"], None, mode))

        keyword_acc = "n/a"
        if answers_mode == mode:
            ok = 0
            for it in answerable:
                ok += it["keyword"].lower() in collect_answer(it["question"], mode).lower()
                time.sleep(2)  # stay under free-tier rate limits
            keyword_acc = f"{ok}/{len(answerable)}"

        rows.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mode": mode,
            "chunk_size": config.CHUNK_SIZE,
            "overlap": config.CHUNK_OVERLAP,
            "final_k": config.FINAL_K,
            "prompt": config.PROMPT_VERSION,
            f"hit@{config.FINAL_K}": f"{hits_at_k}/{len(answerable)}",
            "mrr": round(rr_sum / max(len(answerable), 1), 3),
            "correct_refusals": f"{refused}/{len(unanswerable)}",
            "answer_keyword_acc": keyword_acc,
        })
        print(rows[-1])

    path = Path("eval/results.csv")
    is_new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        if is_new:
            w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--answers", choices=MODES, default=None,
        help="Also run LLM answers for this mode and check keywords (uses API calls).",
    )
    run(ap.parse_args().answers)
