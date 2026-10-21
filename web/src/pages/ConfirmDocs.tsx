import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type Candidate, type Doc } from '../api'

// ts_headline marks hits with <b>…</b>; render them without trusting document text as HTML.
function Snippet({ text }: { text: string }) {
  return <>{text.split(/(<b>.*?<\/b>)/g).map((s, i) =>
    s.startsWith('<b>') ? <mark key={i}>{s.slice(3, -4)}</mark> : <span key={i}>{s}</span>)}</>
}

export default function ConfirmDocs() {
  const id = Number(useParams().id)
  const nav = useNavigate()
  const [review, setReview] = useState<Awaited<ReturnType<typeof api.review>>>()
  const [cands, setCands] = useState<Candidate[]>([])
  const [all, setAll] = useState<Doc[]>([])
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [manual, setManual] = useState<Doc[]>([])
  const [adding, setAdding] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.review(id).then(setReview)
    api.candidates(id).then(c => { setCands(c); setChecked(new Set(c.map(d => d.id))) })
    api.documents().then(setAll)
  }, [id])

  const shown = new Set([...cands.map(c => c.id), ...manual.map(m => m.id)])
  const addable = useMemo(() => all.filter(d => !shown.has(d.id)), [all, cands, manual])
  const toggle = (d: number) => setChecked(s => { const n = new Set(s); n.has(d) ? n.delete(d) : n.add(d); return n })

  const addManual = (docId: number) => {
    const d = all.find(x => x.id === docId)
    if (d) { setManual(m => [...m, d]); setChecked(s => new Set(s).add(d.id)) }
    setAdding('')
  }
  const upload = async (f: File) => {
    try {
      const { id: docId } = await api.upload(f)
      const docs = await api.documents(); setAll(docs)
      const d = docs.find(x => x.id === docId)
      if (d) { setManual(m => [...m, d]); setChecked(s => new Set(s).add(d.id)) }
    } catch (e) { setErr(String(e)) }
  }
  const run = async () => {
    setBusy(true); setErr('')
    try {
      const ids = [...checked]
      await api.confirm(id, ids, manual.map(m => m.id).filter(m => checked.has(m)))
      const job = await api.startJob(id)
      nav(`/jobs/${job.id}`)
    } catch (e) { setErr(String(e)); setBusy(false) }
  }

  if (!review) return <div className="page">Loading…</div>
  return (
    <div className="page narrow">
      <h1>Confirm documents</h1>
      <p className="muted">
        <b>{review.name}</b>: {review.questions.length} questions will be asked of each checked document.
        {review.reference_doc && <> Each is compared against <b>{review.reference_doc.filename}</b>.</>}
        {' '}Nothing outside this list is reviewed, so check that it's complete.
      </p>

      <section className="card">
        <div className="row between">
          <h3>{checked.size} of {shown.size} selected</h3>
          <div className="row">
            <button className="ghost" onClick={() => setChecked(new Set(shown))}>All</button>
            <button className="ghost" onClick={() => setChecked(new Set())}>None</button>
          </div>
        </div>
        <ul className="doclist">
          {cands.map(d => (
            <li key={d.id} className={checked.has(d.id) ? '' : 'off'}>
              <input type="checkbox" checked={checked.has(d.id)} onChange={() => toggle(d.id)} />
              <div>
                <div><a href={api.fileUrl(d.id)} target="_blank" rel="noreferrer">{d.filename}</a>
                  <span className="muted small"> · {d.doc_type}{d.product ? ` · ${d.product}` : ''}</span></div>
                <div className="reasons">
                  {d.reasons.map((r, i) => (
                    <span key={i} className={`reason ${r.kind}`}>
                      <b>{r.kind}</b> {r.kind === 'keyword' ? <Snippet text={r.detail} /> : r.detail}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
          {manual.map(d => (
            <li key={d.id} className={checked.has(d.id) ? '' : 'off'}>
              <input type="checkbox" checked={checked.has(d.id)} onChange={() => toggle(d.id)} />
              <div>
                <div>{d.filename}<span className="muted small"> · {d.doc_type}</span></div>
                <div className="reasons"><span className="reason manual"><b>manual</b> added by you</span></div>
              </div>
            </li>
          ))}
          {!shown.size && <li className="muted">No documents matched. Add some below.</li>}
        </ul>
        <div className="row wrap">
          <select value={adding} onChange={e => e.target.value && addManual(Number(e.target.value))}>
            <option value="">+ Add an existing document…</option>
            {addable.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
          </select>
          <label className="button secondary">Upload PDF
            <input type="file" accept="application/pdf" hidden onChange={e => e.target.files?.[0] && upload(e.target.files[0])} />
          </label>
        </div>
      </section>

      {err && <p className="error">{err}</p>}
      <button className="primary" disabled={!checked.size || busy} onClick={run}>
        Run on {checked.size} documents ({checked.size * review.questions.length} cells) →
      </button>
    </div>
  )
}
