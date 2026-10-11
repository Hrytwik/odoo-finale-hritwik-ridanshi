import { useI18n } from '@/i18n/I18nContext'
import { unitWord } from '@/lib/format'
import type { Tone } from './Badge'

/** A labelled progress bar. `value` and `max` are in the same unit; the bar never overflows its box. */
export function ProgressBar({ label, value, max, tone = 'green', unit }: { label: string; value: number; max: number; tone?: Tone; unit?: string }) {
  const { t } = useI18n()
  const shown = unit === 'kg' || unit === 'm' ? unitWord(unit) : unit
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  return (
    <div className="progress">
      <div className="progress-head">
        <span>{label}</span>
        <span className="muted tabular">
          {t('common.of', { value: `${Math.round(value).toLocaleString('en-IN')}${shown ? ` ${shown}` : ''}`, max: Math.round(max).toLocaleString('en-IN') })}
        </span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={Math.round(max)}
        aria-valuenow={Math.round(Math.min(value, max))}
      >
        <div className={`progress-fill progress-${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
