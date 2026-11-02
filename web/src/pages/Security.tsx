import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type AuditEntry, type System } from '../api'

type Part = { what: string; tool: string; license: string; runs: string; seesText: boolean; external?: boolean }

const ACTIONS: Record<string, string> = {
  ingest: 'Document ingested', create_review: 'Review created', confirm_documents: 'Document set confirmed',
  start_job: 'Job started', extract: 'Model answered', cell_accept: 'Answer accepted', cell_edit: 'Answer edited',
  cell_flag: 'Answer flagged',
}

function entityLink(e: AuditEntry) {
  const [kind, id] = e.entity.split(':')
  const jobId = e.payload.job_id as number | undefined
  if (kind === 'job') return <Link to={`/jobs/${id}`}>job {id}</Link>
  if (kind === 'task' && jobId) return <Link to={`/jobs/${jobId}`}>job {jobId}</Link>
  if (kind === 'review') return <Link to={`/reviews/${id}/confirm`}>review {id}</Link>
  return <span>{kind} {id}</span>
}

export default function Security() {
  const [sys, setSys] = useState<System>()
  useEffect(() => { api.system().then(setSys) }, [])

  const parts: Part[] = [
    { what: 'Original files', tool: 'Local file store (stand-in for S3 / MinIO in your cloud)', license: '-', runs: 'Our server', seesText: true },
    { what: 'PDF parsing + word positions', tool: 'PyMuPDF', license: 'AGPL-3.0 (commercial licence available)', runs: 'Our server', seesText: true },
    { what: 'Database, search, queue, audit log', tool: 'PostgreSQL + pgvector', license: 'PostgreSQL (permissive)', runs: 'Our server', seesText: true },
    { what: 'Embeddings for search', tool: sys?.embed_model ?? '…', license: 'Open-weight model (Apache-2.0)',
      runs: sys?.embed_host.host ?? '…', seesText: true, external: sys?.embed_host.external },
    { what: 'Answer extraction', tool: sys?.extract_model ?? '…', license: 'Open-weight model',
      runs: sys?.extract_host.host ?? '…', seesText: true, external: sys?.extract_host.external },
    { what: 'Quote verification', tool: 'rapidfuzz', license: 'MIT', runs: 'Our server', seesText: true },
    { what: 'PDF viewer + highlights', tool: 'pdf.js (via react-pdf)', license: 'Apache-2.0', runs: "Reviewer's browser", seesText: true },
    { what: 'API / UI', tool: 'FastAPI · React', license: 'MIT', runs: 'Our server', seesText: false },
  ]

  return (
    <div className="page narrow">
      <h1>Security</h1>
      <p className="muted">Where document text goes and what touches it.</p>

      <section className="card">
        <h3>Where your documents go</h3>
        <p className="callout warn small">Both models (answer extraction and search embeddings) run on <b>Fireworks AI</b>, so
          document text is sent to Fireworks for those two steps. Both models are open-weight: in production the same weights
          run on GPUs inside your own cloud and these rows read "ours". Everything else below already runs on our server.</p>
        <table className="plain small">
          <thead><tr><th>Step</th><th>Tool</th><th>Licence</th><th>Runs on</th></tr></thead>
          <tbody>
            {parts.map(p => (
              <tr key={p.what}>
                <td>{p.what}</td><td><code>{p.tool}</code></td><td className="muted">{p.license}</td>
                <td><span className={`badge ${p.external ? 'unverified' : 'answered'}`}>{p.external ? 'external' : 'ours'}</span> {p.runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="small muted">
          <li>No closed-model APIs. Every model has downloadable weights, so nothing depends on a vendor keeping your data.</li>
          <li>Each job records the exact model and prompt version it ran with, and every answer traces back to them.</li>
          <li>The audit log is append-only: the database itself rejects edits and deletes.</li>
          <li>Sign-off requires a named reviewer; anonymous accept/edit/flag is refused.</li>
        </ul>
      </section>

    </div>
  )
}

export function AuditLog() {
  const [log, setLog] = useState<AuditEntry[]>([])
  const [filter, setFilter] = useState('reviewer')
  useEffect(() => { api.auditAll().then(setLog) }, [])

  const shown = useMemo(() => log.filter(e =>
    filter === 'all' ? true : filter === 'reviewer' ? e.action.startsWith('cell_') : e.action === filter), [log, filter])

  const csv = () => {
    const rows = [['time', 'actor', 'action', 'entity', 'model', 'prompt_version', 'note'],
      ...shown.map(e => [e.at, e.actor, e.action, e.entity, String(e.payload.model ?? ''), String(e.payload.prompt_version ?? ''), String(e.payload.note ?? '')])]
    const blob = new Blob([rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\n')], { type: 'text/csv' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'audit_log.csv'; a.click()
  }

  return (
    <div className="page narrow">
      <h1>Audit log</h1>
      <section className="card">
        <div className="row between wrap">
          <p className="muted small">Every action, who took it, and the model and prompt version behind it. Append-only.</p>
          <div className="row">
            <select value={filter} onChange={e => setFilter(e.target.value)}>
              <option value="reviewer">Reviewer sign-offs</option>
              <option value="all">Everything</option>
              {Object.entries(ACTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <button className="secondary" onClick={csv}>Export CSV</button>
          </div>
        </div>
        {!shown.length && <p className="muted small">No entries yet{filter === 'reviewer' ? ': accept, edit or flag an answer on a results page.' : '.'}</p>}
        {shown.length > 0 && (
          <div className="tablewrap">
            <table className="grid">
              <thead><tr><th>When</th><th>Who</th><th>What</th><th>On</th><th>Model</th><th>Prompt</th><th>Note</th></tr></thead>
              <tbody>
                {shown.map(e => (
                  <tr key={e.id}>
                    <td className="nowrap">{new Date(e.at).toLocaleString()}</td>
                    <td>{e.actor}</td>
                    <td>{ACTIONS[e.action] ?? e.action}</td>
                    <td>{entityLink(e)}</td>
                    <td><code>{String(e.payload.model ?? '').split('/').pop() || '-'}</code></td>
                    <td><code>{String(e.payload.prompt_version ?? '') || '-'}</code></td>
                    <td className="muted">{String(e.payload.note ?? '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
