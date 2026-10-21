"""Score a job against data/synthetic/ground_truth.json.
Usage: python scripts/eval.py <job_id>

Per cell: correct / wrong / missed (not_found but answer exists) / correctly not_found.
Also reports the citation verification rate: the share of answered cells whose quotes
were found verbatim in the source PDF."""
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[1]
GT = json.loads((ROOT / "data" / "synthetic" / "ground_truth.json").read_text())


def matches(expected, items: list[str], answer_type: str) -> bool:
    got = " ; ".join(items)
    if answer_type == "boolean":
        want = "yes" if expected else "no"
        return bool(items) and items[0].strip().lower().startswith(want)
    if isinstance(expected, list):  # each expected item must appear in some answer item
        return all(any(fuzz.token_set_ratio(e, g) >= 80 for g in items) for e in expected)
    return fuzz.token_set_ratio(str(expected), got) >= 70


def grounded_in(expected: str, quotes: list[str]) -> bool:
    """A paraphrased text answer counts if its verified evidence is the expected passage."""
    return any(fuzz.partial_ratio(q.lower(), expected.lower()) >= 85 and len(q) >= 25 for q in quotes)


def main(job_id: int) -> None:
    conn = psycopg.connect("postgresql:///arca", row_factory=dict_row)
    rows = conn.execute(
        """SELECT d.filename, q.key, q.answer_type, c.status, c.value,
                  (SELECT bool_or(verified) FROM citations WHERE cell_id=c.id) AS any_verified,
                  (SELECT coalesce(array_agg(quote), '{}') FROM citations WHERE cell_id=c.id AND verified) AS quotes
           FROM cells c JOIN documents d ON d.id=c.doc_id JOIN questions q ON q.id=c.question_id
           WHERE c.job_id=%s ORDER BY d.filename, q.ord""", (job_id,)).fetchall()
    tally = {"correct": 0, "wrong": 0, "missed": 0, "correct_not_found": 0, "hallucinated": 0}
    answered = verified = 0
    for r in rows:
        gt = GT.get(r["filename"], {})
        if r["key"] not in gt:
            continue
        expected = gt[r["key"]]
        items = (r["value"] or {}).get("items", [])
        if r["status"] in ("answered", "unverified"):
            answered += 1
            verified += bool(r["any_verified"])
        # "met" is never stated in letters; a "no" answer is also acceptable there
        if expected is None:
            ok = r["status"] == "not_found" or (r["answer_type"] == "boolean" and items[:1] == ["no"])
            outcome = "correct_not_found" if ok else "hallucinated"
        elif r["status"] == "not_found":
            outcome = "missed"
        else:
            ok = matches(expected, items, r["answer_type"]) or \
                (r["answer_type"] == "text" and isinstance(expected, str) and grounded_in(expected, r["quotes"]))
            outcome = "correct" if ok else "wrong"
        tally[outcome] += 1
        if outcome not in ("correct", "correct_not_found"):
            print(f"  {outcome:<12} {r['filename']:<40} {r['key']:<24} got={items} want={expected}")
    total = sum(tally.values())
    print(f"\njob {job_id}: {total} scored cells")
    for k, v in tally.items():
        print(f"  {k:<18} {v:>4}  ({v / total:.0%})" if total else "")
    if answered:
        print(f"  citation verified  {verified}/{answered} answered cells ({verified / answered:.0%})")


if __name__ == "__main__":
    main(int(sys.argv[1]))
