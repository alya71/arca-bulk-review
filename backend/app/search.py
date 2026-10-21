"""Candidate document search: metadata filters + keyword + semantic, with a reason per hit
so the user can judge why each document was proposed before confirming the set."""
from .llm import embed

SEMANTIC_MIN_SIM = 0.55


def find_candidates(conn, doc_type: str | None, product: str | None, query: str | None, limit: int = 200) -> list[dict]:
    where, params = ["status='ingested'"], {}
    if doc_type:
        where.append("doc_type = %(doc_type)s")
        params["doc_type"] = doc_type
    if product:
        where.append("product = %(product)s")
        params["product"] = product
    docs = conn.execute(f"SELECT * FROM documents WHERE {' AND '.join(where)} ORDER BY filename LIMIT {limit}",
                        params).fetchall()
    by_id = {d["id"]: {**d, "reasons": [], "score": 0.0} for d in docs}
    filt = ", ".join(f"{k}={v}" for k, v in (("doc_type", doc_type), ("product", product)) if v)
    for d in by_id.values():
        if filt:
            d["reasons"].append({"kind": "filter", "detail": filt})

    if query and by_id:
        ids = list(by_id)
        for r in conn.execute(
            """SELECT DISTINCT ON (doc_id) doc_id, ts_rank(tsv, q) AS rank,
                      ts_headline('english', text, q, 'MaxWords=18,MinWords=8') AS snippet
               FROM chunks, websearch_to_tsquery('english', %s) q
               WHERE doc_id = ANY(%s) AND tsv @@ q ORDER BY doc_id, rank DESC""", (query, ids)).fetchall():
            by_id[r["doc_id"]]["reasons"].append({"kind": "keyword", "detail": r["snippet"]})
            by_id[r["doc_id"]]["score"] += r["rank"]
        try:
            vec = str(embed([query], kind="query")[0])
            for r in conn.execute(
                """SELECT doc_id, max(1 - (embedding <=> %s::vector)) AS sim FROM chunks
                   WHERE doc_id = ANY(%s) AND embedding IS NOT NULL GROUP BY doc_id""", (vec, ids)).fetchall():
                if r["sim"] >= SEMANTIC_MIN_SIM:
                    by_id[r["doc_id"]]["reasons"].append({"kind": "semantic", "detail": f"similarity {r['sim']:.2f}"})
                    by_id[r["doc_id"]]["score"] += r["sim"]
        except Exception:
            pass  # semantic search is additive; keyword + filters still work
        if not filt:  # free-text only: drop docs nothing matched
            by_id = {k: v for k, v in by_id.items() if v["reasons"]}

    return sorted(by_id.values(), key=lambda d: (-d["score"], d["filename"]))
