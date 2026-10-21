# Bulk Review

Ask the same questions of many regulatory documents and get a grid of answers. Every claim cites a quote that has been **verified to exist verbatim in the original PDF**, and the quote is highlighted on that PDF.

Self-hosted end to end: Postgres + pgvector, an open-weight model via Ollama, and PyMuPDF. No document leaves the machine.

## Run locally (what the demo uses)

Requires Postgres with pgvector, Ollama, Python 3.11+, and Node 20+.

```bash
ollama serve &                                   # if not already running
ollama pull llama3.1 && ollama pull nomic-embed-text
createdb arca

python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python scripts/gen_synthetic.py   # 16 synthetic PDFs + ground_truth.json
backend/.venv/bin/python scripts/seed.py            # ingest (idempotent by content hash)

cd backend && .venv/bin/uvicorn app.main:app --port 8000 &   # API
cd backend && .venv/bin/python -m app.worker &               # queue worker (run as many as you like)
cd web && npm install && npm run dev                          # UI → http://localhost:5173
```

Or use `docker compose up` (see the header of `docker-compose.yml` for the model-pull and seed commands).

## Demo path
1. **New review** → pick the *CMC excipient grades vs current spec* template (it attaches the current spec as the reference document).
2. **Confirm documents**: each candidate shows *why* it matched (filter / keyword snippet / semantic score). Uncheck any, add more, or upload a PDF.
3. **Results**: the grid fills in as tasks finish. Click a cell to see the answer, the explanation, and each citation (✓ verified / ✕ not found in source). The original PDF opens with the quote highlighted. Accept / Edit / Flag writes to the audit trail.
4. Score the run against ground truth: `backend/.venv/bin/python scripts/eval.py <job_id>`.
5. Headless run without the UI: `backend/.venv/bin/python scripts/run_preset.py ha_commitments`.

## Layout
```
backend/app/ingest/     PyMuPDF word boxes → structure-aware chunks → tags → embeddings
backend/app/extract/    prompt assembly, structured output, citation verification (verify.py)
backend/app/worker.py   Postgres queue (SKIP LOCKED + lease + backoff), idempotent per (job, doc)
backend/app/main.py     API; every state change → audit_log
backend/prompts/        versioned prompts; each job pins model + prompt version
web/src/                3 screens + PDF viewer with highlight overlay
scripts/                synthetic corpus, seed, eval, headless run
```

See [SUMMARY.md](SUMMARY.md) for design decisions and tradeoffs, and [PLAN.md](PLAN.md) for the original plan.
