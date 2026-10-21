-- Bulk review schema. Idempotent: safe to run on every startup.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id            SERIAL PRIMARY KEY,
  sha256        TEXT UNIQUE NOT NULL,          -- raw file lives at blobs/<sha256>.pdf
  filename      TEXT NOT NULL,
  doc_type      TEXT,                          -- cmc | ha_letter | stability_protocol | spec | other
  product       TEXT,
  ectd_section  TEXT,
  title         TEXT,
  page_count    INT,
  status        TEXT NOT NULL DEFAULT 'pending',  -- pending | ingested | error
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Word-level boxes from the raw PDF: the source of truth for highlights.
CREATE TABLE IF NOT EXISTS words (
  doc_id  INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  idx     INT NOT NULL,                        -- global reading-order index within doc
  page    INT NOT NULL,                        -- 0-based
  text    TEXT NOT NULL,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL,          -- PDF points, origin top-left (PyMuPDF)
  PRIMARY KEY (doc_id, idx)
);

CREATE TABLE IF NOT EXISTS chunks (
  id            SERIAL PRIMARY KEY,
  doc_id        INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ord           INT NOT NULL,
  section_path  TEXT,
  text          TEXT NOT NULL,
  page_start    INT NOT NULL,
  page_end      INT NOT NULL,
  word_start    INT NOT NULL,                  -- inclusive, words.idx
  word_end      INT NOT NULL,                  -- inclusive
  embedding     vector(768),
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks(doc_id, ord);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin(tsv);
CREATE INDEX IF NOT EXISTS chunks_emb_idx ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS reviews (
  id                SERIAL PRIMARY KEY,
  name              TEXT NOT NULL,
  doc_filter        JSONB NOT NULL DEFAULT '{}',   -- {doc_type, product, query}
  reference_doc_id  INT REFERENCES documents(id),  -- e.g. current spec for contradiction checks
  created_by        TEXT NOT NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS questions (
  id           SERIAL PRIMARY KEY,
  review_id    INT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  ord          INT NOT NULL,
  key          TEXT NOT NULL,
  prompt       TEXT NOT NULL,
  answer_type  TEXT NOT NULL DEFAULT 'text'        -- text | list | date | boolean
);

-- The confirmed document set. Nothing runs on a document that isn't here.
CREATE TABLE IF NOT EXISTS review_documents (
  review_id  INT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  doc_id     INT NOT NULL REFERENCES documents(id),
  source     TEXT NOT NULL,                        -- search | manual
  added_by   TEXT NOT NULL,
  PRIMARY KEY (review_id, doc_id)
);

CREATE TABLE IF NOT EXISTS jobs (
  id              SERIAL PRIMARY KEY,
  review_id       INT NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  status          TEXT NOT NULL DEFAULT 'running',  -- running | done | failed
  model           TEXT NOT NULL,
  prompt_version  TEXT NOT NULL,
  created_by      TEXT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ
);

-- The queue: one task per (job, document). Workers claim with SKIP LOCKED + lease.
CREATE TABLE IF NOT EXISTS tasks (
  id            SERIAL PRIMARY KEY,
  job_id        INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  doc_id        INT NOT NULL REFERENCES documents(id),
  status        TEXT NOT NULL DEFAULT 'queued',     -- queued | running | done | failed
  attempts      INT NOT NULL DEFAULT 0,
  run_after     TIMESTAMPTZ NOT NULL DEFAULT now(),
  locked_until  TIMESTAMPTZ,
  error         TEXT,
  UNIQUE (job_id, doc_id)
);
CREATE INDEX IF NOT EXISTS tasks_claim_idx ON tasks(status, run_after);

CREATE TABLE IF NOT EXISTS cells (
  id              SERIAL PRIMARY KEY,
  job_id          INT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  doc_id          INT NOT NULL REFERENCES documents(id),
  question_id     INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  value           JSONB,
  status          TEXT NOT NULL,                     -- answered | not_found | unverified | error
  reviewer_state  TEXT NOT NULL DEFAULT 'pending',   -- pending | accepted | edited | flagged
  reviewer        TEXT,
  reviewed_at     TIMESTAMPTZ,
  UNIQUE (job_id, doc_id, question_id)
);

CREATE TABLE IF NOT EXISTS citations (
  id           SERIAL PRIMARY KEY,
  cell_id      INT NOT NULL REFERENCES cells(id) ON DELETE CASCADE,
  doc_id       INT NOT NULL REFERENCES documents(id),
  chunk_id     INT REFERENCES chunks(id),
  quote        TEXT NOT NULL,
  verified     BOOLEAN NOT NULL,
  match_score  REAL,
  page         INT,
  rects        JSONB NOT NULL DEFAULT '[]'          -- [{page,x0,y0,x1,y1}] in PDF points
);

CREATE TABLE IF NOT EXISTS audit_log (
  id       SERIAL PRIMARY KEY,
  actor    TEXT NOT NULL,
  action   TEXT NOT NULL,
  entity   TEXT NOT NULL,
  payload  JSONB NOT NULL DEFAULT '{}',
  at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
