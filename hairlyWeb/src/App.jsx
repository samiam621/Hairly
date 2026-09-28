import { useState } from 'react'
import { request } from './api/client'
import Scanner from './Scanner'
import './App.css'

// Slugs must match the `concerns` table (seeded from backend/db/rules.json).
const CONCERNS = [
  { slug: 'dye allergy', label: 'Dye allergy' },
  { slug: 'color-treated', label: 'Color-treated hair' },
]

export default function App() {
  const [concern, setConcern] = useState('')
  const [barcode, setBarcode] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    setLoading(true)
    setResult(null)
    setError('')
    try {
      setResult(await request('/api/analyze/barcode', { method: 'POST', body: { barcode, concern } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>Hairly</h1>
      {/* `required` on the radios blocks submit natively and tells the user what's missing */}
      <form onSubmit={submit}>
        <fieldset>
          <legend>What are you checking for?</legend>
          {CONCERNS.map((c) => (
            <label key={c.slug}>
              <input
                type="radio"
                name="concern"
                value={c.slug}
                checked={concern === c.slug}
                onChange={() => setConcern(c.slug)}
                required
              />
              {c.label}
            </label>
          ))}
        </fieldset>

        <Scanner onScan={setBarcode} />

        <label>
          Barcode
          <input
            value={barcode}
            onChange={(e) => setBarcode(e.target.value.trim())}
            inputMode="numeric"
            autoComplete="off"
            required
          />
        </label>

        <button disabled={loading}>{loading ? 'Checking…' : 'Check product'}</button>
      </form>

      {error && <p role="alert">{error}</p>}
      {/* ponytail: placeholder until the result-view checklist item */}
      {result && <p>{result.verdict}: {result.summary}</p>}
    </main>
  )
}
