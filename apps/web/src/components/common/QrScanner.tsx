import jsQR from 'jsqr'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input } from '@/components/ui/Field'
import { useI18n } from '@/i18n/I18nContext'
import { parseRollCode } from '@/lib/rollCode'

type Props = { open: boolean; onClose: () => void; onCode: (code: string) => void }

/**
 * Scans a roll's QR tag with the phone camera and calls `onCode` with the roll code. The camera needs HTTPS (or localhost);
 * when it is not available, or a tag is torn, the roll code can be typed instead. Nothing here sends anything to the server.
 */
export function QrScanner({ open, onClose, onCode }: Props) {
  const { t } = useI18n()
  const video = useRef<HTMLVideoElement>(null)
  const [cameraNote, setCameraNote] = useState<string | null>(null)
  const [typed, setTyped] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let stopped = false
    let stream: MediaStream | null = null
    let timer: number | undefined

    async function start() {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setCameraNote(t('scan.noCamera'))
        return
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
        if (stopped) return stream.getTracks().forEach((t) => t.stop())
        const el = video.current
        if (!el) return
        el.srcObject = stream
        await el.play()
        const canvas = document.createElement('canvas')
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        timer = window.setInterval(() => {
          if (!ctx || el.videoWidth === 0) return
          canvas.width = el.videoWidth
          canvas.height = el.videoHeight
          ctx.drawImage(el, 0, 0)
          const frame = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const hit = jsQR(frame.data, frame.width, frame.height)
          const code = hit ? parseRollCode(hit.data) : null
          if (code) onCode(code)
        }, 250)
      } catch {
        setCameraNote(t('scan.cameraFailed'))
      }
    }
    void start()

    return () => {
      stopped = true
      if (timer) window.clearInterval(timer)
      stream?.getTracks().forEach((t) => t.stop())
    }
  }, [open, onCode, t])

  function submitTyped() {
    const code = parseRollCode(typed)
    if (!code) return setError(t('dispatch.notRollCode'))
    setError(null)
    onCode(code)
  }

  return (
    <Dialog open={open} onClose={onClose} title={t('qc.scan')}>
      <div className="stack">
        {cameraNote ? <p className="muted text-sm">{cameraNote}</p> : <video ref={video} muted playsInline className="scanner-video" />}
        <form
          className="stack-sm"
          noValidate
          onSubmit={(e) => {
            e.preventDefault()
            submitTyped()
          }}
        >
          <Field label={t('dispatch.rollCode')} error={error ?? undefined} hint={t('scan.hint')}>
            {(c) => <Input {...c} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" autoCapitalize="characters" />}
          </Field>
          <div className="row">
            <Button type="submit">{t('scan.open')}</Button>
            <Button variant="secondary" onClick={onClose}>
              {t('dispatch.cancel')}
            </Button>
          </div>
        </form>
      </div>
    </Dialog>
  )
}
