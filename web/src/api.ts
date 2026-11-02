export type Question = { id?: number; key: string; prompt: string; answer_type: string; max_words?: number | null }
export type Reason = { kind: 'filter' | 'keyword' | 'semantic'; detail: string }
export type Doc = { id: number; filename: string; doc_type: string; product: string | null; title?: string; page_count?: number }
export type Candidate = Doc & { reasons: Reason[]; score: number }
export type Rect = { page: number; x0: number; y0: number; x1: number; y1: number }
export type Citation = {
  id: number; doc_id: number; filename: string; chunk_id: number | null
  quote: string             // what the model claimed
  source_text: string | null // the PDF's own words for the exact match; the only text shown as a quote
  verified: boolean; match_score: number | null; page: number | null; rects: Rect[]
}
export type Cell = {
  id: number; doc_id: number; question_id: number; status: 'answered' | 'not_found' | 'unverified' | 'error'
  value: { items: string[]; explanation?: string; edited_from?: unknown } | null
  reviewer_state: 'pending' | 'accepted' | 'edited' | 'flagged'; reviewer: string | null; citations: Citation[]
}
export type Job = {
  id: number; review_id: number; status: string; model: string; prompt_version: string; created_by: string
  progress: { status: string; n: number }[]; questions: Question[]
  rows: { doc_id: number; task_status: string; error: string | null; filename: string; product: string | null }[]
  cells: Cell[]
}
export type Preset = { id: string; name: string; doc_filter: Record<string, string>; reference?: string; questions: Question[] }
export type AuditEntry = { id: number; actor: string; action: string; entity: string; payload: Record<string, unknown>; at: string }

export type Host = { host: string; external: boolean }
export type System = { extract_model: string; embed_model: string; extract_host: Host; embed_host: Host }

export const getUser = () => { try { return localStorage.getItem('user') || '' } catch { return '' } }
export const setUser = (u: string) => { try { localStorage.setItem('user', u) } catch { /* private mode */ } }

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-User': getUser() || 'anonymous' }
  if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const r = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...(init.headers as object) } })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? r.statusText)
  return r.json()
}

export const api = {
  presets: () => req<Preset[]>('/presets'),
  documents: (doc_type?: string) => req<Doc[]>(`/documents${doc_type ? `?doc_type=${doc_type}` : ''}`),
  upload: (f: File) => { const fd = new FormData(); fd.append('file', f); return req<{ id: number }>('/documents', { method: 'POST', body: fd }) },
  reviews: () => req<{ id: number; name: string; purpose: string | null; product: string | null; created_by: string; created_at: string; latest_job: number | null; docs: number }[]>('/reviews'),
  createReview: (b: unknown) => req<{ id: number }>('/reviews', { method: 'POST', body: JSON.stringify(b) }),
  review: (id: number) => req<{ id: number; name: string; questions: Question[]; reference_doc: Doc | null; documents: Doc[] }>(`/reviews/${id}`),
  candidates: (id: number) => req<Candidate[]>(`/reviews/${id}/candidates`),
  confirm: (id: number, doc_ids: number[], manual_ids: number[]) =>
    req(`/reviews/${id}/documents`, { method: 'PUT', body: JSON.stringify({ doc_ids, manual_ids }) }),
  startJob: (id: number) => req<{ id: number }>(`/reviews/${id}/jobs`, { method: 'POST' }),
  job: (id: number) => req<Job>(`/jobs/${id}`),
  reviewCell: (id: number, action: string, value?: string[], note?: string) =>
    req(`/cells/${id}/review`, { method: 'POST', body: JSON.stringify({ action, value, note }) }),
  audit: (entity: string) => req<AuditEntry[]>(`/audit?entity=${encodeURIComponent(entity)}`),
  auditAll: () => req<AuditEntry[]>('/audit?limit=1000'),
  system: () => req<System>('/system'),
  fileUrl: (docId: number) => `/api/documents/${docId}/file`,
}
