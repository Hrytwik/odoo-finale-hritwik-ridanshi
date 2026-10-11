import { Camera, Image } from 'lucide-react'
import type { ComponentProps } from 'react'
import { useI18n } from '@/i18n/I18nContext'

/** True on a phone or tablet, where "take a photo now" makes sense. A laptop has no camera button to offer. */
const hasTouch = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches

/**
 * Two ways to add a photo: take one with the camera (phones only), or choose one from the gallery or files.
 * `capture` alone would open only the camera on a phone and only the file list on a laptop, so they are separate buttons.
 * The form field's own props (its id, for the label) go on the gallery input, which is on every device.
 */
export function PhotoInput({ onFile, ...inputProps }: { onFile: (file: File | null) => void } & Omit<ComponentProps<'input'>, 'type' | 'onChange' | 'capture' | 'accept'>) {
  const { t } = useI18n()
  const pick = (input: HTMLInputElement) => {
    onFile(input.files?.[0] ?? null)
    input.value = '' // the same photo can be chosen again
  }
  return (
    <div className="row" style={{ flexWrap: 'wrap' }}>
      {hasTouch() && (
        <label className="file-pick">
          <Camera size={18} aria-hidden />
          <span>{t('photo.camera')}</span>
          <input type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => pick(e.target)} />
        </label>
      )}
      <label className="file-pick">
        <Image size={18} aria-hidden />
        <span>{t('photo.gallery')}</span>
        <input {...inputProps} type="file" accept="image/*" className="sr-only" onChange={(e) => pick(e.target)} />
      </label>
    </div>
  )
}
