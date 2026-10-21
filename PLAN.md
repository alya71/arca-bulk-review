# Plan: Bulk Review MVP (Arca take-home)

## Context
Take-home ([instructions.md](/Users/alinayang/apps/sr_internships/arca/instructions.md)): build a bulk-review product for regulatory docs. It runs N documents × M questions → a grid of structured answers, with a checkable citation for each claim. It must run end to end, and it must have a defensible path to 100k+ concurrent runs.
Priorities from [choices.md](/Users/alinayang/apps/sr_internships/arca/choices.md): **trust over speed**. That means (1) the user confirms or edits the document set, (2) grounding is obvious: the highlight is drawn on the **original raw PDF**, not the parsed text, (3) everything is self-hosted or open source, and every cell is logged (model, prompt version, reviewer).

Decided: Python/FastAPI, Postgres + pgvector, Postgres-backed queue, PyMuPDF, an open-weight local LLM (Ollama), synthetic PDFs. The frontend is minimal for now.

## Core idea: grounding to the raw file
- At ingest, keep the **original PDF bytes** (content-hashed) and extract **word-level boxes** with PyMuPDF (`page.get_text("words")` → page, x0,y0,x1,y1, block/line/word index).
- Chunks are built from those words, so every chunk character maps back to (page, bbox).
- The LLM returns `{value, chunk_id, quote}` for each answer. The backend **verifies** the quote: it normalizes whitespace and case, then fuzzy-matches the quote inside that chunk (rapidfuzz partial ratio ≥ ~90). On a match, the matched span becomes the word bboxes, stored on the citation. No match means the cell is marked `unverified` and gets no fake highlight.
- The UI renders the raw PDF with pdf.js and overlays rectangles in PDF coordinates (scaled to the page's viewport). The parsed text is never what the user sees as evidence.

## Architecture
```
docker-compose: postgres(pgvector) · ollama · api (FastAPI) · worker (N replicas) · web (Vite)
raw files: ./data/blobs/<sha256>.pdf  (local stand-in for S3/MinIO)
```
Flow: upload/seed → ingest task (parse, chunk, tag, embed) → **create review** (questions + doc query) → **candidate docs** (metadata filter + hybrid search) → user confirms the set → **job fans out one task per document** (all M questions in one LLM call) → verify citations → cells stream into the grid → reviewer accepts, edits, or flags → audit log.

### Data model (Postgres)
- `documents(id, sha256, filename, doc_type, product, ectd_section, page_count, status, created_at)`
- `words(doc_id, page, idx, text, x0,y0,x1,y1)`: highlight source of truth (fine at demo scale; prod would store this as a per-doc JSON blob)
- `chunks(id, doc_id, ord, section_path, text, page_start, page_end, word_start, word_end, embedding vector, tsv tsvector)`
- `reviews(id, name, created_by, created_at)`; `questions(id, review_id, key, prompt, answer_type)`, where answer_type is text | enum | list | date | boolean
- `review_documents(review_id, doc_id, added_by, source)`: the **confirmed** set; source is search | manual
- `jobs(id, review_id, status, model, prompt_version, created_at)`
- `tasks(id, job_id, doc_id, status, attempts, locked_until, error)`: the queue
- `cells(id, job_id, doc_id, question_id, value jsonb, status, verified bool, reviewer_state, reviewer, reviewed_at)`, where status is answered | not_found | unverified | error
- `citations(id, cell_id, chunk_id, quote, page, rects jsonb, match_score)`
- `audit_log(id, actor, action, entity, payload jsonb, at)`

### Queue / execution
- Workers poll with `SELECT … FOR UPDATE SKIP LOCKED` plus a lease (`locked_until`). Retries use exponential backoff and a max attempt count. Work is idempotent per (job, doc): cells are upserted.
- A global LLM concurrency cap (semaphore per worker × replica count) gives backpressure.
- Scale story for the walkthrough (not built): move to Temporal for durable fan-out, add per-tenant fair queues, cache results by (doc sha, question, model, prompt_version), batch inserts, PgBouncer, partition `cells`/`chunks` by tenant.

### Extraction
- Provider interface `LLMProvider.extract(doc_chunks, questions, schema) -> list[Answer]`. Ollama implementation uses JSON-schema `format` for structured output. The interface leaves room for Bedrock, Vertex, or Claude later.
- If the document fits the context budget, send the whole thing with chunks labeled `[C12]`. Otherwise retrieve the top-k chunks per question from **within that document** (pgvector + tsvector).
- The prompt requires an explicit `not_found` rather than a guess. Prompt files are versioned (`prompts/extract_v1.txt`), and the version is stored on the job.
- Cross-doc question (the "contradicts current spec?" ask): a review can attach a **reference doc** (the current spec). Its relevant chunks go into every call, and its citations point into the reference PDF. Stretch goal; build it if time allows.

## Minimal frontend (Vite + React + TS, react-pdf)
1. **New review**: name, doc filter (type/product) + search text, questions (key, prompt, type). Presets ship for the three example asks.
2. **Confirm documents**: candidate list with checkboxes, why each matched (filter vs search hit), and "add document". The user must confirm before running.
3. **Results grid + viewer**: rows are docs, columns are questions. Each cell shows its value and a badge (verified / unverified / not found). Clicking a cell opens the raw PDF at the right page with highlight rectangles, plus the quote. Accept/edit/flag buttons write to the audit log. Polling at about 1s is enough for progress (SSE later).

## Repo layout
```
arca/
  docker-compose.yml
  backend/app/{main.py, db.py, models.sql, ingest/{parse_pymupdf.py, chunk.py, tag.py, embed.py},
               search.py, extract/{provider.py, ollama.py, verify.py}, worker.py, routes/*.py}
  backend/prompts/extract_v1.txt
  scripts/gen_synthetic.py      # reportlab → PDFs + ground_truth.json
  scripts/seed.py               # ingest all synthetic docs
  web/src/{pages/NewReview.tsx, ConfirmDocs.tsx, Results.tsx, components/PdfViewer.tsx}
  SUMMARY.md                    # one-pager: shape, rejected options, tradeoffs, next week
```

## Build order (~2h)
0. Copy this plan to `arca/PLAN.md` (first action after approval)
1. compose + schema + blob store (15m)
2. synthetic generator: ~6 CMC, ~5 HA letters, ~4 stability protocols, 1 "current spec" with 2 planted contradictions, plus ground_truth.json (20m)
3. ingest: PyMuPDF words → chunks → tags (filename/heading rules first, LLM tag optional) → embeddings with `nomic-embed-text` via Ollama (20m)
4. queue worker + Ollama extraction + quote verification (30m)
5. API routes + 3 pages + PDF highlight overlay (30m)
6. SUMMARY.md + eval script comparing cells to ground_truth (5–10m)

## Open choices (decide as we go)
- **Local model**: e.g. Qwen3 8B or Llama 3.1 8B, depending on laptop RAM. Pick it by running the eval script, not by feel. Smaller models make quote verification even more important.
- **Embeddings**: `nomic-embed-text` (768-dim) via Ollama, vs skipping vectors for the demo (metadata + tsvector only). Leaning toward including them since they're cheap.
- **Doc tagging**: rules from synthetic filenames/headings (fast) vs an LLM classifier (more realistic). Rules for the MVP; describe the classifier in the walkthrough.
- **Highlight granularity**: word-level rects merged per line (planned) vs whole-block rects (simpler fallback).
- **Edits by reviewer**: does an edited value need its own citation? Proposed: yes. The reviewer either keeps the original citation or marks it "manual, no citation", and the audit log records which.
- **Progress transport**: polling (MVP) vs SSE.
- **Context budget threshold** for whole-doc vs retrieval mode; depends on the model's context window (e.g. 32k).

## Verification
- `docker compose up`, `ollama pull <model> nomic-embed-text`, `python scripts/gen_synthetic.py && python scripts/seed.py`.
- In the UI, run the "CMC excipients" preset → confirm docs → watch cells fill → click a cell → the raw PDF opens at the cited page with the highlight on the exact text.
- `python scripts/eval.py <job_id>`: accuracy against ground_truth.json, and the verified-citation rate. Check that a corrupted-quote unit test yields `unverified`.
- Kill a worker mid-job and check that its leased tasks are retried and the job completes (shows durability).
- Check that `audit_log` holds the model, prompt version, and reviewer action for an accepted cell.
