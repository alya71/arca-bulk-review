# Bulk Review

Ask the same questions of many regulatory documents and get a grid of answers. Every claim cites a quote that has been **verified to exist verbatim in the original PDF**, and the quote is highlighted on that PDF.

Open-weight models only, with no closed-model APIs: Postgres + pgvector, PyMuPDF, and either Ollama (fully local; no document leaves the machine) or Kimi K3 hosted on Fireworks for the demo.

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

**Model:** by default extraction runs on llama3.1 through Ollama. To use a hosted open-weight model through Fireworks, create `arca/.env`:
```bash
FIREWORKS_API_KEY=fw_...
EXTRACT_MODEL=accounts/fireworks/models/kimi-k3   # any accounts/... id routes to Fireworks
```
Each job records the model it ran with. Embeddings always run locally via Ollama. With a hosted model, raise `WORKER_CONCURRENCY` (e.g. 8).

`docker-compose.yml` is included but untested; the native setup above is the supported path.

## Demo path
1. **New review** → pick the *Excipient grade audit* template (it attaches the current spec as the reference document).
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
