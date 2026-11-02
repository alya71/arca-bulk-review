import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Doc, type Preset, type Question } from '../api'

const DOC_TYPES = ['', 'cmc', 'ha_letter', 'stability_protocol', 'spec', 'other']
const ANSWER_TYPES = ['text', 'list', 'date', 'boolean']

export default function NewReview() {
  const nav = useNavigate()
  const [presets, setPresets] = useState<Preset[]>([])
  const [specs, setSpecs] = useState<Doc[]>([])
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof api.reviews>>>([])
  const [name, setName] = useState('')
  const [docType, setDocType] = useState('')
  const [product, setProduct] = useState('')
  const [query, setQuery] = useState('')
  const [refId, setRefId] = useState<number | ''>('')
  const [questions, setQuestions] = useState<Question[]>([{ key: '', prompt: '', answer_type: 'text' }])
  const [err, setErr] = useState('')

  useEffect(() => {
    api.presets().then(setPresets)
    api.documents('spec').then(setSpecs)
    api.reviews().then(setRecent)
  }, [])

  const applyPreset = (p: Preset) => {
    setName(p.name); setDocType(p.doc_filter.doc_type ?? ''); setProduct(p.doc_filter.product ?? '')
    setQuery(p.doc_filter.query ?? ''); setQuestions(p.questions.map(q => ({ ...q })))
    setRefId(p.reference ? (specs[0]?.id ?? '') : '')
  }
  const setQ = (i: number, patch: Partial<Question>) => setQuestions(qs => qs.map((q, j) => (j === i ? { ...q, ...patch } : q)))

  const submit = async () => {
    setErr('')
    const qs = questions.filter(q => q.key.trim() && q.prompt.trim())
    if (!name.trim() || !qs.length) return setErr('A name and at least one question are required.')
    try {
      const { id } = await api.createReview({
        name, questions: qs, reference_doc_id: refId || null,
        doc_filter: Object.fromEntries(Object.entries({ doc_type: docType, product, query }).filter(([, v]) => v)),
      })
      nav(`/reviews/${id}/confirm`)
    } catch (e) { setErr(String(e)) }
  }

  return (
    <div className="page narrow">
      <h1>New bulk review</h1>
      <p className="muted">Ask the same questions of many documents. You'll confirm the document set before anything runs.</p>

      <section className="card">
        <h3>Start from a template</h3>
        <div className="row wrap">
          {presets.map(p => <button key={p.id} className="secondary" onClick={() => applyPreset(p)}>{p.name}</button>)}
        </div>
      </section>

      <section className="card">
        <label>Review name<input value={name} onChange={e => setName(e.target.value)} /></label>
        <h3>Which documents?</h3>
        <div className="grid3">
          <label>Document type
            <select value={docType} onChange={e => setDocType(e.target.value)}>
              {DOC_TYPES.map(t => <option key={t} value={t}>{t || 'any'}</option>)}
            </select>
          </label>
          <label>Product<input value={product} placeholder="e.g. HT-204" onChange={e => setProduct(e.target.value)} /></label>
          <label>Search text<input value={query} placeholder="keywords / description" onChange={e => setQuery(e.target.value)} /></label>
        </div>
        <label>Reference document (optional, compared against each document)
          <select value={refId} onChange={e => setRefId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">none</option>
            {specs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
          </select>
        </label>
      </section>

      <details className="card qs">
        <summary>
          <h3>Questions <span className="muted small">
            ({questions.filter(q => q.key.trim()).length}, asked of every document{questions.some(q => q.key.trim()) ? `: ${questions.filter(q => q.key.trim()).map(q => q.key).join(', ')}` : ''})
          </span></h3>
        </summary>
        {questions.map((q, i) => (
          <div key={i} className="question">
            <input className="qkey" value={q.key} placeholder="column_key" onChange={e => setQ(i, { key: e.target.value })} />
            <select value={q.answer_type} onChange={e => setQ(i, { answer_type: e.target.value })}>
              {ANSWER_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <textarea value={q.prompt} rows={2} placeholder="What do you want to know?" onChange={e => setQ(i, { prompt: e.target.value })} />
            <button className="ghost" title="Remove" onClick={() => setQuestions(qs => qs.filter((_, j) => j !== i))}>✕</button>
            <label className="maxw">Max words
              <input type="number" min={1} placeholder="optional" value={q.max_words ?? ''}
                onChange={e => setQ(i, { max_words: e.target.value ? Math.max(1, Number(e.target.value)) : null })} />
            </label>
          </div>
        ))}
        <button className="secondary" onClick={() => setQuestions(qs => [...qs, { key: '', prompt: '', answer_type: 'text' }])}>+ Add question</button>
      </details>

      {err && <p className="error">{err}</p>}
      <button className="primary" onClick={submit}>Find documents →</button>

      {recent.length > 0 && (
        <section className="card">
          <h3>Recent reviews</h3>
          <table className="plain">
            <tbody>
              {recent.map(r => (
                <tr key={r.id}>
                  <td>{r.name}</td><td className="muted small">{r.docs} docs · {r.created_by}</td>
                  <td>{r.latest_job ? <Link to={`/jobs/${r.latest_job}`}>results</Link> : <Link to={`/reviews/${r.id}/confirm`}>confirm docs</Link>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
