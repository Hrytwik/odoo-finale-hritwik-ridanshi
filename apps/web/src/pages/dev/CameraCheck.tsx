import { useRef, useState } from 'react'

/** Dev-only page: does live camera work on a phone over our local HTTPS? */
export default function CameraCheck() {
  const video = useRef<HTMLVideoElement>(null)
  const [status, setStatus] = useState('not started')
  const secure = window.isSecureContext

  async function start() {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setStatus('Live camera blocked: this page is not a secure context. Use the photo button below.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      if (video.current) {
        video.current.srcObject = stream
        await video.current.play()
      }
      setStatus('Live camera works')
    } catch (err) {
      setStatus(`Camera error: ${(err as Error).name}`)
    }
  }

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <h1>Camera check</h1>
      <p>
        Secure context: <strong>{String(secure)}</strong>
      </p>
      <button type="button" onClick={start}>
        Start live camera
      </button>
      <video ref={video} muted playsInline style={{ width: '100%', maxWidth: 448, border: '1px solid #ccc' }} />
      <label style={{ display: 'grid', gap: 4 }}>
        <span>Fallback: take a photo</span>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => setStatus(`Photo chosen: ${e.target.files?.[0]?.name ?? 'none'}`)}
        />
      </label>
      <p data-testid="status">
        <strong>{status}</strong>
      </p>
    </div>
  )
}
