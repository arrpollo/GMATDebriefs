import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    with (ROOT / name).open(encoding="utf-8") as f:
        return json.load(f)


debriefs = load("debriefs.json")
details = load("post_details.json")
summaries = load("summaries.json")
reddit = load("reddit_corpus.json")
club = load("corpus_index.json")


def body_for(post_id):
    detail = details.get(post_id, {})
    return "\n\n".join(str(detail.get(k, "") or "") for k in ("body", "overview", "sections") if detail.get(k))


def richness(row):
    post_id = row["post_id"]
    return (row.get("total_score") or 0) + (row.get("n_replies") or 0) * 5 + len(body_for(post_id)) / 200


def rank(limit=20):
    rows = [r for r in debriefs if r["post_id"] not in summaries and r["post_id"] != "1rrulke"]
    rows.sort(key=richness, reverse=True)
    for r in rows[:limit]:
        pid = r["post_id"]
        print(f"{pid}\t{richness(r):.1f}\tscore={r.get('total_score')}\treplies={r.get('n_replies')}\tsrc={r.get('source')}\tlen={len(body_for(pid))}\t{r.get('title')}")


def read(post_id):
    row = next((r for r in debriefs if r["post_id"] == post_id), {})
    detail = details.get(post_id, {})
    print("=" * 100)
    print(post_id, row.get("source"), row.get("total_score"), row.get("title"))
    print("Q/V/DI:", row.get("q_score"), row.get("v_score"), row.get("di_score"))
    print("=" * 100)
    for key in ("body", "overview", "sections"):
        if detail.get(key):
            print(f"\n--- {key.upper()} ---\n{detail[key]}")
    corpus = reddit if post_id in reddit else club
    entry = corpus.get(post_id, {})
    print("\n--- CORPUS BODY ---")
    print(entry.get("text") or entry.get("body") or "")
    print("\n--- REPLIES ---")
    for i, rep in enumerate(entry.get("replies") or [], 1):
        print(f"\n[{i}] {rep.get('author')}\n{rep.get('text') or ''}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "read":
        for post_id in sys.argv[2:]:
            read(post_id)
    else:
        rank(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
