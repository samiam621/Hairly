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

// A button that opens the camera for one still photo of the ingredient list.
// The real <input type="file"> is hidden; the button just clicks it, so it looks like the other buttons.
function LabelButton({ onPhoto }) {
  const input = useRef(null)

  function pick(e) {
    const photo = e.target.files[0]
    e.target.value = '' // so retaking and picking the same file still fires onChange
    if (photo) onPhoto(photo)
  }

  return (
    <>
      <button type="button" onClick={() => input.current.click()}>Scan label</button>
      {/* capture="environment" opens the rear camera on phones; desktops get a file picker */}
      <input ref={input} type="file" accept="image/*" capture="environment" hidden onChange={pick} />
    </>
  )
}

export default function App() {
  const [concern, setConcern] = useState('')
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
    } finally {
      busy.current = false
      setLoading(false)
    }
  }

  // Barcode: the backend looks it up on Open Beauty Facts. Runs the moment the scanner reads a code.
  function checkBarcode(barcode) {
    run(() => request('/api/analyze/barcode', { method: 'POST', body: { barcode, concern } }))
  }

  // Label: the backend has Gemini read the ingredient list off the photo.
  function checkLabel(photo) {
    const form = new FormData() // multipart form, the shape FastAPI's File()/Form() params expect
    form.append('image', photo)
    form.append('concern', concern)
    run(() => request('/api/analyze/label', { method: 'POST', body: form }))
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
    // No ingredients from Open Beauty Facts: send them to the label scan instead.
    // It's a button, not automatic: browsers only open the camera from a tap.
    screen = (
      <section>
        {/* 503 = Open Beauty Facts was unreachable, so the product may exist */}
        <h2>{error.status === 503 ? "Couldn't look this product up" : 'No ingredients on file'}</h2>
        <p>{error.message}</p>
        <LabelButton onPhoto={checkLabel} />
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
          <Scanner onScan={checkBarcode}>
            <LabelButton onPhoto={checkLabel} />
          </Scanner>
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
