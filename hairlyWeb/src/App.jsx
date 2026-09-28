import { useRef, useState } from 'react'
import { request } from './api/client'
import Result from './Result'
import Scanner from './Scanner'
import './App.css'

// Slugs must match the `concerns` table (seeded from backend/db/rules.json).
const CONCERNS = [
  { slug: 'dye allergy', label: 'Dye allergy' },
  { slug: 'color-treated', label: 'Color-treated hair' },
]

export default function App() {
  const [concern, setConcern] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null) // ApiError
  const busy = useRef(false) // `loading` lands a render late, so a double tap could slip past it

  // Runs the moment the scanner reads a code; there's no separate submit step.
  async function check(barcode) {
    if (busy.current) return
    busy.current = true
    setLoading(true)
    setError(null)
    try {
      setResult(await request('/api/analyze/barcode', { method: 'POST', body: { barcode, concern } }))
    } catch (err) {
      setError(err)
    } finally {
      busy.current = false
      setLoading(false)
    }
  }

  // Back to the scanner; the chosen concern stays for the next product.
  function scanAnother() {
    setResult(null)
    setError(null)
  }

  let screen
  if (result) {
    screen = <Result result={result} onScanAnother={scanAnother} />
  } else if (error?.code === 'PRODUCT_NOT_FOUND') {
    screen = (
      <section>
        {/* 503 = Open Beauty Facts was unreachable, so the product may exist */}
        <h2>{error.status === 503 ? "Couldn't look this product up" : 'Product not found'}</h2>
        <p>{error.message}</p>
        {/* ponytail: the label-photo button arrives with Phase 4's POST /api/analyze/label */}
        <button type="button" onClick={scanAnother}>Scan a different product</button>
      </section>
    )
  } else {
    screen = (
      <section>
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
              />
              {c.label}
            </label>
          ))}
        </fieldset>

        {/* A scan checks right away, so no concern means no scanner yet */}
        {loading ? (
          <p role="status">Checking…</p>
        ) : concern ? (
          <Scanner onScan={check} />
        ) : (
          <p>Pick what you're checking for to start scanning.</p>
        )}
        {error && <p role="alert">{error.message}</p>}
      </section>
    )
  }

  return (
    <main>
      <header>
        <h1>Hairly</h1>
        <p>Ingredient check for your hair</p>
      </header>
      {screen}
    </main>
  )
}
