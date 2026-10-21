import { StrictMode, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './index.css'
import { getUser, setUser } from './api'
import NewReview from './pages/NewReview'
import ConfirmDocs from './pages/ConfirmDocs'
import Results from './pages/Results'

function Shell() {
  const [user, setU] = useState(getUser())
  return (
    <BrowserRouter>
      <header className="topbar">
        <Link to="/" className="brand">Bulk Review</Link>
        <span className="muted small">Self-hosted · open-weight model · every action audited</span>
        <label className="user">
          Reviewer
          <input value={user} placeholder="your name" onChange={e => { setU(e.target.value); setUser(e.target.value) }} />
        </label>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<NewReview />} />
          <Route path="/reviews/:id/confirm" element={<ConfirmDocs />} />
          <Route path="/jobs/:id" element={<Results />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><Shell /></StrictMode>)
