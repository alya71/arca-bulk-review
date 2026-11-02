"""Headless end-to-end run of a preset through the API: create review → candidates →
confirm → start job → wait. Usage: python scripts/run_preset.py cmc_excipients [question_key=max_words ...]"""
import sys
import time

import httpx

API = "http://localhost:8000/api"
H = {"X-User": "demo-script"}


def main(preset_id: str, max_words: dict[str, int] | None = None) -> int:
    c = httpx.Client(base_url=API, headers=H, timeout=60)
    p = next(p for p in c.get("/presets").json() if p["id"] == preset_id)
    for q in p["questions"]:
        q["max_words"] = (max_words or {}).get(q["key"])
    ref = None
    if p.get("reference"):
        ref = next(d["id"] for d in c.get("/documents", params={"doc_type": p["reference"]}).json())
    rid = c.post("/reviews", json={"name": p["name"], "doc_filter": p["doc_filter"], "reference_doc_id": ref,
                                   "questions": p["questions"]}).json()["id"]
    cands = c.get(f"/reviews/{rid}/candidates").json()
    for d in cands:
        print(f"  candidate {d['id']:>3} {d['filename']:<45} {[r['kind'] for r in d['reasons']]}")
    c.put(f"/reviews/{rid}/documents", json={"doc_ids": [d["id"] for d in cands]})
    jid = c.post(f"/reviews/{rid}/jobs").json()["id"]
    print(f"review {rid}, job {jid}")
    while True:
        j = c.get(f"/jobs/{jid}").json()
        print("  ", {r["status"]: r["n"] for r in j["progress"]})
        if j["status"] != "running":
            break
        time.sleep(5)
    return jid


if __name__ == "__main__":
    limits = {k: int(v) for k, v in (a.split("=") for a in sys.argv[2:])}
    print("job", main(sys.argv[1] if len(sys.argv) > 1 else "cmc_excipients", limits))
