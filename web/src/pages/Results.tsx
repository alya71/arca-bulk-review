import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, type AuditEntry, type Cell, type Citation, type Job } from '../api'
import PdfViewer from '../components/PdfViewer'

const STATUS_LABEL: Record<string, string> = {
  answered: 'verified', unverified: 'unverified', not_found: 'not found', error: 'error',
}

const norm = (s: string) => s.toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"')
  .replace(/[‐-―]/g, '-').replace(/\s+/g, ' ').replace(/^[\s"'.,;:]+|[\s"'.,;:]+$/g, '')

// An answer item is verbatim when it appears word-for-word inside one of the cell's verified quotes
// (which were themselves matched against the PDF). Everything else is the model's wording.
const isVerbatim = (item: string, c: Cell) => {
  const n = norm(item)
  return n.length >= 3 && c.citations.some(ci => ci.verified && norm(ci.quote).includes(n))
}

// For free-text answers the model tends to stitch sentences together with small rewordings.
// If any item isn't verbatim, show the verified quotes (exact by construction) instead,
// and keep the model's wording as a labelled summary.
const display = (c: Cell, answerType?: string) => {
  const items = c.value?.items ?? []
  const quotes = c.citations.filter(ci => ci.verified).map(ci => ci.quote)
  const paraphrased = answerType === 'text' && quotes.length > 0 && items.some(v => !isVerbatim(v, c))
  return { items: paraphrased ? [...new Set(quotes)] : items, summary: paraphrased ? items : null }
}

function Item({ text, cell, tag }: { text: string; cell: Cell; tag?: boolean }) {
  const v = isVerbatim(text, cell)
  return <span className={v ? 'verbatim' : undefined} title={v ? 'Exact text from the document' : 'Model wording; check the evidence'}>
    {v ? <>“{text}”</> : text}
    {tag && <span className={`vtag ${v ? 'exact' : 'model'}`}>{v ? 'exact quote' : 'model wording'}</span>}
  </span>
}

export default function Results() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const [job, setJob] = useState<Job>()
  const [sel, setSel] = useState<number | null>(null)       // selected cell id
  const [cite, setCite] = useState<Citation | null>(null)   // citation whose doc is shown
  const [viewDoc, setViewDoc] = useState<number | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const j = await api.job(id)
      if (!alive) return
      setJob(j)
      if (j.status === 'running') setTimeout(tick, 2000)
    }
    tick()
    return () => { alive = false }
  }, [id])

  const cellAt = useMemo(() => {
    const m = new Map<string, Cell>()
    job?.cells.forEach(c => m.set(`${c.doc_id}:${c.question_id}`, c))
    return m
  }, [job])
  const cell = job?.cells.find(c => c.id === sel) ?? null
  const question = job?.questions.find(q => q.id === cell?.question_id)

  const selectCell = (c: Cell) => {
    setSel(c.id)
    setParams({ cell: String(c.id) }, { replace: true })  // deep link to this claim's evidence
    const first = c.citations.find(ci => ci.verified) ?? c.citations[0] ?? null
    setCite(first)
    setViewDoc(first?.doc_id ?? c.doc_id)
    api.audit(`cell:${c.id}`).then(setAudit)
  }

  useEffect(() => {
    const want = Number(params.get('cell'))
    const c = want && sel == null ? job?.cells.find(x => x.id === want) : undefined
    if (c) selectCell(c)
  }, [job])  // eslint-disable-line react-hooks/exhaustive-deps

  // Highlight every verified quote of this cell that lives in the document being viewed.
  const rects = useMemo(() => (cell?.citations ?? [])
    .filter(ci => ci.verified && ci.doc_id === viewDoc).flatMap(ci => ci.rects), [cell, viewDoc])

  const act = async (action: 'accept' | 'edit' | 'flag') => {
    if (!cell) return
    let value: string[] | undefined, note: string | undefined
    if (action === 'edit') {
      const v = prompt('Corrected value (one item per line):', (cell.value?.items ?? []).join('\n'))
      if (v == null) return
      value = v.split('\n').map(s => s.trim()).filter(Boolean)
      note = prompt('Reason for the edit (kept in the audit log):') ?? undefined
    }
    if (action === 'flag') { note = prompt('What is wrong?') ?? undefined; if (note == null) return }
    try { await api.reviewCell(cell.id, action, value, note) } catch (e) { alert((e as Error).message); return }
    setJob(await api.job(id))
    setAudit(await api.audit(`cell:${cell.id}`))
  }

  if (!job) return <div className="page">Loading…</div>
  const prog = Object.fromEntries(job.progress.map(p => [p.status, p.n]))
  const total = job.rows.length
  const counts = job.cells.reduce<Record<string, number>>((a, c) => ({ ...a, [c.status]: (a[c.status] ?? 0) + 1 }), {})
  const reviewed = job.cells.filter(c => c.reviewer_state !== 'pending').length

  return (
    <div className="results">
      <div className="grid-pane">
        <div className="row between wrap">
          <h2>Job #{job.id}</h2>
          <span className="muted small">model <code>{job.model}</code> · prompt <code>{job.prompt_version}</code> · started by {job.created_by}</span>
        </div>
        <div className="row wrap small">
          <span className={`pill ${job.status}`}>{job.status}</span>
          <span>{prog.done ?? 0}/{total} documents</span>
          <span className="badge answered">{counts.answered ?? 0} verified</span>
          <span className="badge unverified">{counts.unverified ?? 0} unverified</span>
          <span className="badge not_found">{counts.not_found ?? 0} not found</span>
          <span className="muted">{reviewed}/{job.cells.length} reviewed</span>
        </div>
        <div className="tablewrap">
          <table className="grid">
            <thead>
              <tr><th>Document</th>{job.questions.map(q => <th key={q.id} title={q.prompt}>{q.key}</th>)}</tr>
            </thead>
            <tbody>
              {job.rows.map(r => (
                <tr key={r.doc_id}>
                  <th className="docname">
                    <button className="link" onClick={() => { setSel(null); setCite(null); setViewDoc(r.doc_id) }}>{r.filename}</button>
                    {r.task_status !== 'done' && <div className={`pill ${r.task_status}`}>{r.task_status}</div>}
                    {r.error && <div className="error small" title={r.error}>failed: see tooltip</div>}
                  </th>
                  {job.questions.map(q => {
                    const c = cellAt.get(`${r.doc_id}:${q.id}`)
                    if (!c) return <td key={q.id} className="pending">{r.task_status === 'failed' ? '-' : '…'}</td>
                    const { items } = display(c, q.answer_type)
                    return (
                      <td key={q.id} className={`cell ${c.status} ${c.id === sel ? 'sel' : ''} rv-${c.reviewer_state}`} onClick={() => selectCell(c)}>
                        <span className={`dot ${c.status}`} title={STATUS_LABEL[c.status]} />
                        {c.status === 'not_found' ? <span className="muted">not found</span> :
                          items.length > 1
                            ? <ul>{items.map((v, i) => <li key={i}><Item text={v} cell={c} /></li>)}</ul>
                            : items[0] != null && <Item text={items[0]} cell={c} />}
                        {c.reviewer_state !== 'pending' && <span className={`rv ${c.reviewer_state}`}>{c.reviewer_state}</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>

      <div className="viewer-pane">
        {cell && question && (
          <section className="detail">
            <div className="row between">
              <div className="row">
                <b title={question.prompt}>{question.key}</b>
                <span className={`badge ${cell.status}`}>{STATUS_LABEL[cell.status]}</span>
                {question.max_words && (cell.value?.items ?? []).some(v => v.split(/\s+/).length > question.max_words!) &&
                  <span className="badge error">over {question.max_words}-word limit</span>}
              </div>
              <div className="row">
                <button className="primary" onClick={() => act('accept')}>Accept</button>
                <button className="secondary" onClick={() => act('edit')}>Edit</button>
                <button className="danger" onClick={() => act('flag')}>Flag</button>
              </div>
            </div>
            {/* The answer itself is in the grid cell; here only the model's reasoning, minus its internal chunk labels. */}
            {(cell.value?.explanation || display(cell, question.answer_type).summary) &&
              <p className="small muted why">{display(cell, question.answer_type).summary?.join(' ')
                ?? cell.value!.explanation.replace(/\[?\b[CR]\d+\b\]?/g, m => m.includes('R') ? 'the reference' : 'the document')
                  .replace(/^./, c => c.toUpperCase())}</p>}
            <div className="row wrap">
              <span className="small muted">Evidence:</span>
              {!cell.citations.length && <span className="small muted">none</span>}
              {/* Verified quotes are shown where they live, on the PDF; these just jump to them. */}
              {cell.citations.filter(ci => ci.verified).map((ci, i) => (
                <button key={ci.id} className={`jump ${cite?.id === ci.id ? 'sel' : ''}`} title={ci.quote}
                  onClick={() => { setCite(ci); setViewDoc(ci.doc_id) }}>
                  ✓ {i + 1} · {ci.doc_id !== cell.doc_id ? 'reference ' : ''}p.{(ci.page ?? 0) + 1}
                </button>
              ))}
              {audit.length > 0 && (
                <details className="small audit-d">
                  <summary>history ({audit.length})</summary>
                  <ul className="audit">
                    {audit.map(a => <li key={a.id}><b>{a.actor}</b> {a.action.replace('cell_', '')} · {new Date(a.at).toLocaleString()}
                      {typeof a.payload.note === 'string' && a.payload.note && <> · “{a.payload.note}”</>}</li>)}
                  </ul>
                </details>
              )}
            </div>
            {/* Unverified quotes have no highlight, so their text is the only thing to show. */}
            {cell.citations.filter(ci => !ci.verified).map(ci => (
              <div key={ci.id} className="citation bad small">
                <span>✕ Quote not found in the source; nothing to highlight</span>
                <q>{ci.quote}</q>
              </div>
            ))}
          </section>
        )}
        {viewDoc ? (
          <>
            <div className="viewer-head small">
              <b>{job.rows.find(r => r.doc_id === viewDoc)?.filename ?? cite?.filename}</b>
              <span className="muted"> · original file{rects.length ? ` · ${rects.length} highlighted line${rects.length > 1 ? 's' : ''}` : ''}</span>
              <a href={api.fileUrl(viewDoc)} target="_blank" rel="noreferrer">open ↗</a>
            </div>
            <div className="viewer-scroll">
              <PdfViewer url={api.fileUrl(viewDoc)} rects={rects} focusPage={cite?.page ?? rects[0]?.page ?? null} />
            </div>
          </>
        ) : <p className="muted center">Click a cell to see its evidence highlighted in the original document.</p>}
      </div>
    </div>
  )
}
