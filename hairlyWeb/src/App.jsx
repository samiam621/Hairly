import { useRef, useState } from 'react'
import { request } from './api/client'
import LabelCamera from './LabelCamera'
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
  const [labelMode, setLabelMode] = useState(false) // true = label camera showing instead of the barcode scanner
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null) // ApiError
  const busy = useRef(false) // `loading` lands a render late, so a double tap could slip past it

  // Shared by both scans: `send` makes the API call, run() handles loading, result and error.
  async function run(send) {
    if (busy.current) return
    busy.current = true
    setLoading(true)
    setError(null)
    try {
      setResult(await send())
    } catch (err) {
      setError(err)
      // Open Beauty Facts has no ingredients (or is down): switch straight to the label camera
      if (err.code === 'PRODUCT_NOT_FOUND') setLabelMode(true)
    } finally {
      busy.current = false
      setLoading(false)
    }
  }

  // Barcode: the backend looks it up on Open Beauty Facts. Runs the moment the scanner reads a code.
  function checkBarcode(barcode) {
    run(() => request('/api/analyze/barcode', { method: 'POST', body: { barcode, concern } }))
  }

  // Label: the backend has Gemini read the ingredient list off every photo together.
  function checkLabel(photos) {
    setLabelMode(false) // closes the camera; "Checking…" shows while the AI reads
    const form = new FormData() // multipart form, the shape FastAPI's File()/Form() params expect
    photos.forEach((photo) => form.append('image', photo)) // same field once per photo
    form.append('concern', concern)
    run(() => request('/api/analyze/label', { method: 'POST', body: form }))
  }

  // Back to the scanner; the chosen concern stays for the next product.
  function scanAnother() {
    setResult(null)
    setError(null)
    setLabelMode(false)
  }

  let screen
  if (result) {
    screen = <Result result={result} onScanAnother={scanAnother} />
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

        {/* Above the camera, so "no ingredients on file" or "retake the photo" is seen first */}
        {error && <p role="alert">{error.message}</p>}

        {/* A scan checks right away, so no concern means no scanner yet */}
        {loading ? (
          <p role="status">Checking…</p>
        ) : !concern ? (
          <p>Pick what you're checking for to start scanning.</p>
        ) : labelMode ? (
          <LabelCamera onPhotos={checkLabel} onCancel={scanAnother} />
        ) : (
          <Scanner onScan={checkBarcode}>
            <button type="button" onClick={() => setLabelMode(true)}>Scan label</button>
          </Scanner>
        )}
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
