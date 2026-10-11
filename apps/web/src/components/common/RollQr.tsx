import { QRCodeSVG } from 'qrcode.react'
import { useI18n } from '@/i18n/I18nContext'
import { rollUrl } from '@/lib/rollCode'

/** The roll's QR tag: scanning it opens `/r/<code>`. The code is printed under the square for when a tag cannot be scanned. */
export function RollQr({ code, size = 128 }: { code: string; size?: number }) {
  const { t } = useI18n()
  return (
    <figure className="roll-qr">
      <QRCodeSVG value={rollUrl(code)} size={size} marginSize={1} role="img" aria-label={t('rollQr.alt', { code })} />
      <figcaption>{code}</figcaption>
    </figure>
  )
}
