# Bulk Review: design summary

**What it is:** a tool that runs N regulatory documents × M questions → a grid of answers. Each cell is backed by a quote that is **checked to exist verbatim in the original PDF** and highlighted there. Design priority: **trust over speed**. A reviewer should never have to take the model's word for anything.

## The shape I chose
```
upload ─► ingest (PyMuPDF words+boxes → section chunks → tags → embeddings) ─► Postgres
review = questions + document filter (+ optional reference doc, e.g. current spec)
       ─► candidate search (filter + keyword + semantic, with "why it matched")
       ─► HUMAN CONFIRMS THE DOCUMENT SET
       ─► job fans out 1 task per document (all M questions in one structured call)
       ─► worker: LLM → verify every quote against the PDF's words → cells + citations + rects
       ─► grid + original-PDF viewer with highlights ─► accept / edit / flag ─► audit_log
```

**Key decisions**
| Decision | Why | Rejected |
|---|---|---|
| **Highlight on the raw PDF** using word boxes kept at ingest | Evidence is the source document, not our parse of it | Showing parsed text/markdown snippets: an extra layer the reviewer has to trust |
| **Verify every quote exactly**, then display the PDF's own words | The model can produce plausible but false citations. A quote counts only if it appears verbatim (ignoring case, spacing, curly vs straight quotes); one changed word means `unverified`. The text shown in quote marks is the document's matched words, never the model's copy | Fuzzy matching (a one-word paraphrase can pass), or trusting model-provided page numbers / chunk IDs |
| **The user confirms the document set** before running, with match reasons | In bulk review, a missed document is a silent failure | Fully automatic RAG over the corpus |
| **Whole document in context; retrieval only above a budget** | Recall beats token cost; most CMC sections, letters, and protocols fit | Per-question top-k RAG everywhere (loses recall silently) |
| **One task = one document, all questions** | Document is read once, tasks are idempotent, retries are cheap | One task per cell (M× the prompt tokens) |
| **Evidence-first JSON schema** (citations → value → status) | With constrained decoding, a small model that emits `status` first bails out with `not_found`. Measured: 0/24 → 13/24 correct | Status-first schema |
| **Comparison column before the yes/no** for the spec-contradiction check | Gives the model room to reason, and gives the reviewer the per-excipient reasoning to check | A bare boolean question |
| **Postgres as everything** (data, vectors, queue, audit) | One stateful system to secure, back up, and get through vendor review; SKIP LOCKED queues scale further than people expect | Separate vector DB + Redis/Celery for an MVP |
| **Open-weight models on Fireworks** (Kimi K3 for extraction, nomic-embed-text for search), behind an `LLMProvider` interface | Open weights mean production can run the same models in the customer's cloud, which pharma security review requires; Fireworks is the demo host. A local 8B model (llama 3.1 via Ollama, the first baseline) was too weak and too slow | Closed-model APIs; local-only small models |
| **Evidence-repair pass**: answers with no verified quote get one focused "quote it" retry | The model sometimes answers correctly but skips citations. The retry's quotes go through the same verifier, so it recovers evidence without manufacturing trust. Costs a second call only when needed | Accepting uncited answers, or requiring `minItems: 1` up front (forces fake quotes on `not_found`) |
| **Job pins model + prompt version** | Reproducibility: every cell traces to exact model + prompt; found and fixed a bug where the API stamped one version and the worker ran another | Global "current prompt" |

## Evidence the spine works
- End to end on 16 synthetic PDFs (6 CMC, 1 current spec with **2 planted contradictions**, 5 HA letters, 4 stability protocols), with `ground_truth.json`.
- `scripts/eval.py <job>` scores correctness and the citation-verification rate. **Results: see the table below.**
- Durability test: killed the worker mid-job (job #3). Tasks 15 and 16 were re-claimed exactly at lease expiry (attempt 2) and the job completed. Re-runs replace a document's cells atomically, so double processing is harmless.

**Baseline results** (llama3.1 8B on a laptop via Ollama, since replaced by Kimi K3; `scripts/eval.py`):
| Ask | Job | Correct | Citations verified | Notes |
|---|---|---|---|---|
| CMC excipients vs spec (6 docs × 4 scored) | #3 | 17/24 (71%) | 21/24 | Both planted contradictions caught, but 3/4 clean products over-flagged (see below). Justifications sometimes cite boilerplate |
| HA commitments (5 × 4) | #4 | 18/20 (90%) | 17/17 | Correctly says "not found" for *has it been met?* on all 5. 2 misses: returned a role ("Regulatory Project Manager") where no named owner exists |
| Stability protocols (4 × 6) | #6 | 24/24 (100%) | 24/24 | Before the evidence-repair pass (#5): 24/24 values correct but **0 cited**, all shown as `unverified`. The safety net held |

**Same pipeline, same prompt (extract_v2), Kimi K3 (open-weight, via Fireworks):**
| Ask | Job | Correct | Citations verified | Wall time (all docs, 8 worker threads) |
|---|---|---|---|---|
| CMC excipients vs spec | #8 | 24/24 (100%) | 24/24 | 42 s |
| HA commitments | #9 | 20/20 (100%; 7 of these are correct "not found") | 18/18 | 52 s |
| Stability protocols | #7 | 24/24 (100%) | 24/24 | 22 s |

Kimi K3 fixes the over-flagging on brand names and the role-vs-person misses, and finishes each preset in under a minute instead of 10–15 (about $0.70 for all three). The caveat: the synthetic set is now saturated, so it no longer tells models apart on accuracy. The next eval needs harder, real-shaped documents. Embeddings still run locally. In production, the K3 weights would run in the customer's cloud (vLLM or a dedicated deployment), not on a shared API.

Iteration log: v1 prompt 0/24 on CMC (status-first schema) → v2 evidence-first 13/24 → evidence-aware scoring 17/24 → evidence repair took stability from 0% to 100% verified.

**Why CMC contradictions over-flag:** the `spec_comparison` column makes it visible. The 8B model lists *"Croscarmellose sodium: conflict (Ac-Di-Sol vs NF)"*, treating a brand name as a conflict despite the instruction. A reviewer spots it in seconds. The fix is architectural, not a prompt tweak: the LLM extracts (excipient, grade) pairs from both documents, and **code** does the comparison with explicit normalization rules.

## Scaling to 100k+ concurrent tasks (designed, not load-tested)
- **The bottleneck is model throughput, not the app.** Workers are stateless and scale horizontally (`--scale worker=N`). A global concurrency cap (per-process semaphore × replicas) is the backpressure valve. Production would add a token-bucket limiter per model endpoint.
- **Queue:** Postgres SKIP LOCKED handles thousands of claims/sec. Beyond that, or for multi-step workflows (e.g. extract → cross-check → escalate), move to **Temporal**: the task is already an idempotent activity.
- **Fairness:** per-tenant queues / weighted claiming, so one 300k-cell job can't starve a 160-cell one.
- **Cost and latency:** cache by (doc sha, question hash, model, prompt version); batch inserts; PgBouncer; partition `cells`/`chunks` by tenant; words → per-doc blob in object storage instead of rows.
- **Models:** an open-weight 70B on vLLM (in the customer's VPC), or Bedrock/Vertex where allowed. Small models for tagging, large ones for extraction.

## Known gaps (honest)
- The original llama3.1 8B baseline was the quality ceiling: it truncates lists, paraphrases, and over-calls contradictions. The verification layer catches false *citations*, not wrong *reasoning*, which is why the human accept/flag step exists.
- Tables are read row-flattened (fine for these documents; real CMC tables need layout-aware parsing, e.g. Docling).
- Auth is an `X-User` header; no SSO/RBAC. No Part 11 e-signature on accept.
- docker-compose is written but not tested in this session (Docker wasn't running); the demo runs natively.

## With another week
1. **Deterministic cross-document checks:** the LLM extracts structured facts, and code compares them against the spec with normalization rules (grade synonyms, brand ↔ generic), so "contradicts spec" isn't an 8B judgment call.
2. **Eval harness:** 50+ labelled real-shaped documents, CI on prompt/model changes, per-question accuracy, and a confidence → review-queue triage (show reviewers the low-confidence cells first).
3. **Bigger/better model routing** (70B or Claude via Bedrock where allowed) and a second-pass "verifier" model on yes/no and cross-document questions.
4. **Layout-aware parsing** (Docling) for tables and scans (OCR), keeping the word-box contract.
5. **Temporal + per-tenant fairness + result caching**, then a real load test against a mocked LLM to find the next bottleneck.
6. **Product:** saved question templates, re-run only changed documents, diff between runs, export to Excel with citation links, SSO + e-signatures for Part 11.
