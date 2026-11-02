"""Run one task: answer all of a review's questions for one document, then verify every citation."""
from pathlib import Path

from ..llm import LLMProvider, embed
from .verify import locate, rects_for

PROMPT_VERSION = "extract_v2"  # default for new jobs; each job pins its own version
PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(version: str) -> str:
    return (PROMPT_DIR / f"{version}.txt").read_text()
WHOLE_DOC_WORD_BUDGET = 6000  # ~8k tokens; above this, retrieve top chunks per question instead
TOP_K = 4


def answer_schema(keys: list[str]) -> dict:
    item = {
        "type": "object",
        "properties": {
            # Evidence first, verdict last: with constrained decoding, emitting status first lets
            # small models bail out with "not_found" before they've looked for anything.
            "citations": {"type": "array", "items": {
                "type": "object",
                "properties": {"chunk": {"type": "string"}, "quote": {"type": "string"}},
                "required": ["chunk", "quote"]}},
            "value": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string"},
            "status": {"type": "string", "enum": ["answered", "not_found"]},
        },
        "required": ["citations", "value", "explanation", "status"],
    }
    return {"type": "object", "properties": {k: item for k in keys}, "required": keys}


def _select_chunks(conn, doc_id: int, questions: list[dict]) -> list[dict]:
    chunks = conn.execute("SELECT * FROM chunks WHERE doc_id=%s ORDER BY ord", (doc_id,)).fetchall()
    if sum(len(c["text"].split()) for c in chunks) <= WHOLE_DOC_WORD_BUDGET:
        return chunks  # whole document: best recall, one call answers every question
    # Large document: hybrid retrieval *within this document only*, union across questions.
    keep: set[int] = set()
    for q in questions:
        vec = embed([q["prompt"]], kind="query")[0]
        rows = conn.execute(
            """SELECT id FROM chunks WHERE doc_id=%s
               ORDER BY (embedding <=> %s::vector) - 0.1 * ts_rank(tsv, plainto_tsquery('english', %s)) LIMIT %s""",
            (doc_id, str(vec), q["prompt"], TOP_K)).fetchall()
        keep |= {r["id"] for r in rows}
    return [c for c in chunks if c["id"] in keep]


def _reference_chunks(conn, ref_doc_id: int, product: str | None) -> list[dict]:
    chunks = conn.execute("SELECT * FROM chunks WHERE doc_id=%s ORDER BY ord", (ref_doc_id,)).fetchall()
    if product:  # only the part of the reference relevant to this product, plus its preamble
        chunks = [c for c in chunks if c["ord"] == 0 or product in c["text"]]
    return chunks


def _fmt(label: str, c: dict) -> str:
    sec = f" · {c['section_path']}" if c["section_path"] else ""
    return f"[{label}{c['ord']}] (page {c['page_start'] + 1}{sec})\n{c['text']}"


def run_task(conn, provider: LLMProvider, job: dict, review: dict, doc: dict, questions: list[dict]) -> list[dict]:
    """Returns cell dicts: {question_id, status, value, explanation, citations:[...]}."""
    chunks = _select_chunks(conn, doc["id"], questions)
    ref_chunks = _reference_chunks(conn, review["reference_doc_id"], doc["product"]) if review["reference_doc_id"] else []

    def limit(q: dict) -> str:  # soft limit: a hard cut (maxLength) would break verbatim quotes mid-sentence
        return (f" LENGTH LIMIT: every value item must be {q['max_words']} words or fewer. This overrides any "
                f"instruction to copy whole sentences: copy only the shortest contiguous phrase that answers the "
                f"question (citations may still quote the full sentence).") if q.get("max_words") else ""
    qs = "\n".join(f"- {q['key']} ({q['answer_type']}): {q['prompt']}{limit(q)}" for q in questions)
    # Questions before and after the document: the model reads knowing what to look for.
    parts = [f"QUESTIONS:\n{qs}", f"DOCUMENT: {doc['filename']}\n\n" + "\n\n".join(_fmt("C", c) for c in chunks)]
    if ref_chunks:
        parts.append("REFERENCE (current specification, compare the DOCUMENT against it):\n\n"
                     + "\n\n".join(_fmt("R", c) for c in ref_chunks))
    parts.append(f"Now answer each question using the text above:\n{qs}")
    out = provider.generate_json(load_prompt(job["prompt_version"]), "\n\n---\n\n".join(parts), answer_schema([q["key"] for q in questions]))

    by_label = {f"C{c['ord']}": c for c in chunks} | {f"R{c['ord']}": c for c in ref_chunks}
    words_cache: dict[int, list[dict]] = {}

    def words_of(doc_id: int) -> list[dict]:
        if doc_id not in words_cache:
            words_cache[doc_id] = conn.execute(
                "SELECT idx, page, text, x0, y0, x1, y1 FROM words WHERE doc_id=%s ORDER BY idx", (doc_id,)).fetchall()
        return words_cache[doc_id]

    def verify(raw_cites: list[dict]) -> list[dict]:
        cites = []
        for c in raw_cites:
            label = c.get("chunk", "").strip("[] ")
            quote = c.get("quote", "").strip()
            chunk = by_label.get(label)
            target_doc = chunk["doc_id"] if chunk else (review["reference_doc_id"] if label.startswith("R") else doc["id"])
            ws = words_of(target_doc) if target_doc else []
            m, located_in = None, None
            if chunk:  # first look where the model said it was...
                m = locate(quote, [w for w in ws if chunk["word_start"] <= w["idx"] <= chunk["word_end"]])
                located_in = chunk["id"] if m else None
            if not m and ws:  # ...then anywhere in that document (model may mislabel the chunk)
                m = locate(quote, ws)
            cites.append({
                "doc_id": target_doc, "chunk_id": located_in or (chunk["id"] if chunk else None), "quote": quote,
                "verified": m is not None, "match_score": m.score if m else None,
                "rects": rects_for(ws, m.word_start, m.word_end) if m else [],
            })
        return cites

    answers = {q["key"]: out.get(q["key"]) or {"status": "not_found", "value": [], "explanation": "", "citations": []}
               for q in questions}
    cites = {k: verify(a.get("citations", [])) for k, a in answers.items()}

    # Evidence repair: an answer with no verified quote gets one focused retry that asks only
    # for supporting quotes. The new quotes go through the same verification, so this can
    # rescue evidence that was skipped, never manufacture trust.
    missing = [q for q in questions if answers[q["key"]].get("status") == "answered"
               and answers[q["key"]].get("value") and not any(c["verified"] for c in cites[q["key"]])]
    if missing:
        ask = "\n".join(f"- {q['key']}: {q['prompt']} ANSWER GIVEN: {'; '.join(answers[q['key']]['value'])}"
                        for q in missing)
        repair_schema = {"type": "object", "required": [q["key"] for q in missing], "properties": {
            q["key"]: {"type": "object", "required": ["citations"], "properties": {"citations": {
                "type": "array", "minItems": 1, "items": {
                    "type": "object", "required": ["chunk", "quote"],
                    "properties": {"chunk": {"type": "string"}, "quote": {"type": "string"}}}}}}
            for q in missing}}
        fixed = provider.generate_json(
            load_prompt(job["prompt_version"]),
            "\n\n---\n\n".join(parts[1:-1] + [
                f"These answers were extracted from the text above but are missing evidence. For each, copy the "
                f"exact sentence(s) or table row(s) that support it, with their chunk label:\n{ask}"]),
            repair_schema)
        for q in missing:
            cites[q["key"]] += verify((fixed.get(q["key"]) or {}).get("citations", []))

    cells = []
    for q in questions:
        a = answers[q["key"]]
        if a.get("status") == "not_found" or not a.get("value"):
            status = "not_found"
        elif any(c["verified"] for c in cites[q["key"]]):
            status = "answered"
        else:
            status = "unverified"  # an answer with no checkable evidence is never shown as answered
        cells.append({"question_id": q["id"], "status": status,
                      "value": {"items": a.get("value", []), "explanation": a.get("explanation", ""),
                                "evidence_repaired": q in missing},
                      "citations": cites[q["key"]]})
    return cells
