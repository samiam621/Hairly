import { BrowserMultiFormatReader } from '@zxing/browser'
import { useEffect, useRef, useState } from 'react'

const reader = new BrowserMultiFormatReader()

const CAMERA_ERRORS = {
  NotAllowedError: 'Camera access is blocked. Allow it in your browser settings, or upload a photo of the barcode.',
  NotFoundError: 'No camera found. Upload a photo of the barcode instead.',
  NotReadableError: 'The camera is in use by another app. Close it and try again, or upload a photo.',
}

// Reads a barcode from the camera, or from an uploaded photo when the camera is blocked or missing.
export default function Scanner({ onScan, children }) {
  const videoRef = useRef(null)
  const controlsRef = useRef(null)
  const onScanRef = useRef(onScan)
  const [camera, setCamera] = useState('off') // off | starting | on
  const [error, setError] = useState('')

  useEffect(() => () => controlsRef.current?.stop(), []) // release the camera when leaving the screen
  // The camera callback outlives renders; this way it sees the concern picked now, not when the camera started.
  useEffect(() => {
    onScanRef.current = onScan
  })

  function stopCamera() {
    controlsRef.current?.stop()
    controlsRef.current = null
    setCamera('off')
  }

  // Started from the click, not an effect: StrictMode's double effect would open two streams on one <video>.
  async function startCamera() {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      // Also what a phone gets over plain http: browsers only allow the camera on HTTPS or localhost.
      setError("This browser can't use the camera here. Upload a photo of the barcode instead.")
      return
    }
    setCamera('starting')
    let found = false
    try {
      const controls = await reader.decodeFromVideoDevice(undefined, videoRef.current, (result, _err, scanControls) => {
        if (!result) return
        // zxing tries the first frame before the await above returns, so stop via scanControls, not controlsRef
        found = true
        scanControls.stop()
        controlsRef.current = null
        setCamera('off')
        onScanRef.current(result.getText())
      })
      if (!found) {
        controlsRef.current = controls
        setCamera('on')
      }
    } catch (err) {
      setCamera('off')
      setError(CAMERA_ERRORS[err?.name] ?? "Couldn't start the camera. Upload a photo of the barcode instead.")
    }
  }

  async function scanPhoto(e) {
    const file = e.target.files[0]
    e.target.value = '' // so picking the same file again still fires onChange
    if (!file) return
    setError('')
    const url = URL.createObjectURL(file)
    try {
      onScan((await reader.decodeFromImageUrl(url)).getText())
    } catch {
      setError('No barcode found in that photo. Try a closer, sharper shot.')
    } finally {
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="scanner">
      <video ref={videoRef} hidden={camera === 'off'} muted playsInline />
      <div className="scan-options">
        {camera === 'on' ? (
          <button type="button" onClick={stopCamera}>Stop camera</button>
        ) : (
          <button type="button" onClick={startCamera} disabled={camera === 'starting'}>
            {camera === 'starting' ? 'Starting camera…' : 'Scan barcode'}
          </button>
        )}
        {children /* whatever App puts between <Scanner> tags: the Scan label button */}
      </div>
      <label>
        Or upload a photo of the barcode
        <input type="file" accept="image/*" onChange={scanPhoto} />
      </label>
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
