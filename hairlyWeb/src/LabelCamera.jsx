import { useEffect, useRef, useState } from 'react'

// Browsers only allow the camera on HTTPS or localhost, so a phone on plain http lands here too.
const supported = Boolean(navigator.mediaDevices?.getUserMedia)

// Live camera for the ingredient label: line it up, tap Take photo, and the still goes to onPhoto.
export default function LabelCamera({ onPhoto, onCancel }) {
  const videoRef = useRef(null)
  const [ready, setReady] = useState(false) // true once the preview is showing a picture
  const [error, setError] = useState('')

  // Open the rear camera when this appears; close it when it goes away (photo taken or cancelled).
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
            ? 'Camera access is blocked. Allow it in your browser settings, or upload a photo of the label.'
            : "Couldn't start the camera. Upload a photo of the label instead.",
        ),
      )
    return () => {
      closed = true
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  // Copy the current video frame onto a canvas, then save it as a JPEG for the AI to read.
  function takePhoto() {
    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth // the camera's full resolution, not the smaller on-screen preview
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    canvas.toBlob((photo) => photo && onPhoto(photo), 'image/jpeg', 0.9) // JPEG keeps it well under the upload limit
  }

  function pickPhoto(e) {
    const photo = e.target.files[0]
    e.target.value = '' // so picking the same file again still fires onChange
    if (photo) onPhoto(photo)
  }

  const live = supported && !error

  return (
    <div className="scanner">
      {live && <video ref={videoRef} autoPlay muted playsInline onPlaying={() => setReady(true)} />}
      <div className="scan-options">
        {live && (
          <button type="button" onClick={takePhoto} disabled={!ready}>
            {ready ? 'Take photo' : 'Starting camera…'}
          </button>
        )}
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
      <label>
        Or upload a photo of the label
        <input type="file" accept="image/*" onChange={pickPhoto} />
      </label>
      {!supported && <p role="alert">This browser can't use the camera here. Upload a photo of the label instead.</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
