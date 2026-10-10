import { QRCodeSVG } from 'qrcode.react'
import { rollUrl } from '@/lib/rollCode'

/** The roll's QR tag: scanning it opens `/r/<code>`. The code is printed under the square for when a tag cannot be scanned. */
export function RollQr({ code, size = 128 }: { code: string; size?: number }) {
  return (
    <figure className="roll-qr">
      <QRCodeSVG value={rollUrl(code)} size={size} marginSize={1} role="img" aria-label={`QR code for roll ${code}`} />
      <figcaption>{code}</figcaption>
    </figure>
  )
}
