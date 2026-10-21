import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { api, type AuditEntry, type Cell, type Citation, type Job } from '../api'
import PdfViewer from '../components/PdfViewer'

const STATUS_LABEL: Record<string, string> = {
  answered: 'verified', unverified: 'unverified', not_found: 'not found', error: 'error',
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
    await api.reviewCell(cell.id, action, value, note)
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
                    return (
                      <td key={q.id} className={`cell ${c.status} ${c.id === sel ? 'sel' : ''} rv-${c.reviewer_state}`} onClick={() => selectCell(c)}>
                        <span className={`dot ${c.status}`} title={STATUS_LABEL[c.status]} />
                        {c.status === 'not_found' ? <span className="muted">not found</span> :
                          (c.value?.items ?? []).length > 1
                            ? <ul>{c.value!.items.map((v, i) => <li key={i}>{v}</li>)}</ul>
                            : <span>{c.value?.items[0]}</span>}
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
          <section className="card detail">
            <div className="row between">
              <h3>{question.key}</h3>
              <span className={`badge ${cell.status}`}>{STATUS_LABEL[cell.status]}</span>
            </div>
            <p className="muted small">{question.prompt}</p>
            {cell.value?.items.length ? <ul>{cell.value.items.map((v, i) => <li key={i}>{v}</li>)}</ul> : <p className="muted">No answer found in this document.</p>}
            {cell.value?.explanation && <p className="small"><i>{cell.value.explanation}</i></p>}
            <h4>Evidence</h4>
            {!cell.citations.length && <p className="muted small">No citations.</p>}
            {cell.citations.map(ci => (
              <button key={ci.id} className={`citation ${ci.verified ? 'ok' : 'bad'} ${cite?.id === ci.id ? 'sel' : ''}`}
                onClick={() => { setCite(ci); setViewDoc(ci.doc_id) }}>
                <span className="small">{ci.verified ? `✓ found verbatim (${Math.round(ci.match_score ?? 0)}%)` : '✕ quote not found in source'}
                  {' · '}{ci.filename}{ci.page != null ? ` p.${ci.page + 1}` : ''}</span>
                <q>{ci.quote}</q>
              </button>
            ))}
            <div className="row">
              <button className="primary" onClick={() => act('accept')}>Accept</button>
              <button className="secondary" onClick={() => act('edit')}>Edit</button>
              <button className="danger" onClick={() => act('flag')}>Flag</button>
            </div>
            {audit.length > 0 && (
              <details>
                <summary className="small">Audit trail ({audit.length})</summary>
                <ul className="audit small">
                  {audit.map(a => <li key={a.id}><b>{a.actor}</b> {a.action.replace('cell_', '')} · {new Date(a.at).toLocaleString()}
                    {typeof a.payload.note === 'string' && a.payload.note && <> · “{a.payload.note}”</>}</li>)}
                </ul>
              </details>
            )}
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
