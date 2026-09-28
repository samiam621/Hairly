import { useEffect, useRef, useState } from 'react'

// Browsers only allow the camera on HTTPS or localhost, so a phone on plain http lands here too.
const supported = Boolean(navigator.mediaDevices?.getUserMedia)
const MAX_PHOTOS = 10 // same cap as the backend (gemini.MAX_PHOTOS)

// Live camera for the ingredient label: take a photo of each side the list wraps around, then tap Done.
export default function LabelCamera({ onPhotos, onCancel }) {
  const videoRef = useRef(null)
  const [ready, setReady] = useState(false) // true once the preview is showing a picture
  const [error, setError] = useState('')
  const [photos, setPhotos] = useState([]) // [{ blob, url }]: blob is sent, url shows the thumbnail
  const urls = useRef([]) // every thumbnail URL made, so they can all be freed at the end

  // Open the rear camera when this appears; close it when it goes away (Done or Cancel).
  useEffect(() => {
    if (!supported) return
    let stream
    let closed = false // StrictMode mounts twice in dev: a camera that opens after cleanup must be closed, not leaked
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } } }) // rear camera, enough pixels for small print
      .then((s) => {
        if (closed) return s.getTracks().forEach((t) => t.stop())
        stream = s
        videoRef.current.srcObject = s
      })
      .catch((err) =>
        setError(
          err?.name === 'NotAllowedError'
            ? 'Camera access is blocked. Allow it in your browser settings, or upload photos of the label.'
            : "Couldn't start the camera. Upload photos of the label instead.",
        ),
      )
    return () => {
      closed = true
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  // A thumbnail URL keeps its photo in memory until revoked, so free them all when this closes.
  useEffect(() => () => urls.current.forEach((url) => URL.revokeObjectURL(url)), [])

  function add(blobs) {
    const added = blobs.map((blob) => ({ blob, url: URL.createObjectURL(blob) }))
    urls.current.push(...added.map((p) => p.url))
    setPhotos((p) => [...p, ...added].slice(0, MAX_PHOTOS))
  }

  // Copy the current video frame onto a canvas and save it as a JPEG; the camera stays open for the next angle.
  function takePhoto() {
    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth // the camera's full resolution, not the smaller on-screen preview
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    canvas.toBlob((photo) => photo && add([photo]), 'image/jpeg', 0.9) // JPEG keeps each one small
  }

  function pickPhotos(e) {
    const picked = [...e.target.files] // copy first: clearing the input empties its file list
    e.target.value = '' // so picking the same file again still fires onChange
    add(picked)
  }

  const live = supported && !error

  return (
    <div className="scanner">
      {live && <video ref={videoRef} autoPlay muted playsInline onPlaying={() => setReady(true)} />}
      <p>Take a photo of each side the ingredient list wraps around, then tap Done.</p>

      {photos.length > 0 && (
        <ul className="shots">
          {photos.map((p, i) => (
            <li key={p.url}>
              <img src={p.url} alt={`Photo ${i + 1}`} />
            </li>
          ))}
        </ul>
      )}

      {live && (
        <button type="button" onClick={takePhoto} disabled={!ready || photos.length >= MAX_PHOTOS}>
          {ready ? 'Take photo' : 'Starting camera…'}
        </button>
      )}
      <div className="scan-options">
        {/* Every angle goes to the AI together, so it can stitch one full list */}
        <button type="button" onClick={() => onPhotos(photos.map((p) => p.blob))} disabled={photos.length === 0}>
          Done ({photos.length})
        </button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>

      <label>
        Or upload photos of the label
        <input type="file" accept="image/*" multiple onChange={pickPhotos} />
      </label>
      {!supported && <p role="alert">This browser can't use the camera here. Upload photos of the label instead.</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
