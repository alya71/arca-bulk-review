import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Doc, type Preset, type Question } from '../api'

const ANSWER_TYPES = ['text', 'list', 'date', 'boolean']
const human = (key: string) => key.replace(/_/g, ' ')

export default function NewReview() {
  const nav = useNavigate()
  const [presets, setPresets] = useState<Preset[]>([])
  const [docs, setDocs] = useState<Doc[]>([])
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof api.reviews>>>([])
  const [preset, setPreset] = useState<Preset | null>(null)
  const [product, setProduct] = useState('')
  const [purpose, setPurpose] = useState('')
  const [questions, setQuestions] = useState<Question[]>([])
  const [err, setErr] = useState('')

  useEffect(() => {
    api.presets().then(setPresets)
    api.documents().then(setDocs)
    api.reviews().then(setRecent)
  }, [])

  // Products that actually have documents of this template's type.
  const products = useMemo(() => [...new Set(docs
    .filter(d => d.product && d.doc_type === preset?.doc_filter.doc_type).map(d => d.product!))].sort(), [docs, preset])

  const choose = (p: Preset) => { setPreset(p); setProduct(''); setQuestions(p.questions.map(q => ({ ...q }))) }
  const setQ = (i: number, patch: Partial<Question>) => setQuestions(qs => qs.map((q, j) => (j === i ? { ...q, ...patch } : q)))

  const submit = async () => {
    setErr('')
    if (!preset) return setErr('Choose a task.')
    if (!purpose.trim()) return setErr('Add a purpose: it is kept with the review for the audit trail.')
    const qs = questions.filter(q => q.key.trim() && q.prompt.trim())
    // The template decides the document type, search terms and reference spec; the user only narrows by product.
    const ref = preset.reference ? docs.find(d => d.doc_type === preset.reference)?.id ?? null : null
    try {
      const { id } = await api.createReview({
        name: preset.name, purpose, questions: qs, reference_doc_id: ref,
        doc_filter: { ...preset.doc_filter, ...(product ? { product } : {}) },
      })
      nav(`/reviews/${id}/confirm`)
    } catch (e) { setErr(String(e)) }
  }

  return (
    <div className="page narrow">
      <h1>New bulk review</h1>

      <section className="card">
        <h3>Task</h3>
        <div className="templates">
          {presets.map(p => (
            <button key={p.id} className={`template ${preset?.id === p.id ? 'sel' : ''}`} onClick={() => choose(p)}>
              <b>{p.name}</b>
              <span className="muted small">({p.questions.map(q => human(q.key)).join(', ')})</span>
            </button>
          ))}
        </div>
      </section>

      {preset && <>
        <section className="card">
          <div className="grid2">
            <label>Product
              <select value={product} onChange={e => setProduct(e.target.value)}>
                <option value="">All products ({products.length})</option>
                {products.map(p => <option key={p}>{p}</option>)}
              </select>
            </label>
            <label>Purpose
              <input value={purpose} placeholder="e.g. Q3 spec change impact assessment" onChange={e => setPurpose(e.target.value)} />
            </label>
          </div>
        </section>

        <details className="card qs">
          <summary>
            <h3>Questions <span className="muted small">({questions.map(q => human(q.key)).join(', ')})</span></h3>
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
      </>}

      {recent.length > 0 && (
        <section className="card">
          <h3>Recent reviews</h3>
          <table className="plain">
            <tbody>
              {recent.map(r => (
                <tr key={r.id}>
                  <td>{r.name}{r.product ? ` · ${r.product}` : ''}{r.purpose && <div className="muted small">{r.purpose}</div>}</td>
                  <td className="muted small">{r.docs} docs · {r.created_by}</td>
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
