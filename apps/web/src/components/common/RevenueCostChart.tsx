import { useI18n } from '@/i18n/I18nContext'
import { niceScale, yFor } from '@/lib/chart'
import { formatLakh, formatMoney } from '@/lib/format'

export type OrderPoint = { label: string; revenue: number; cost: number; profit: number }

const H = 300
const PAD = { top: 52, right: 16, bottom: 34, left: 64 }
/** Room for one order: enough for its two bars and a two-line profit label. */
const PER_ORDER = 86

/**
 * Revenue and cost side by side for each order, with the profit (or loss) written above it.
 * Plain SVG: it follows the light and dark colours and has a table for screen readers.
 */
export function RevenueCostChart({ data, caption }: { data: OrderPoint[]; caption: string }) {
  const { t } = useI18n()
  const W = Math.max(640, PAD.left + PAD.right + data.length * PER_ORDER)
  const scale = niceScale(data.flatMap((d) => [d.revenue, d.cost]))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const band = plotW / Math.max(data.length, 1)
  const group = Math.min(band * 0.7, 130)
  const barW = (group - 14) / 2
  const cx = (i: number) => PAD.left + band * i + band / 2
  const y = (v: number) => PAD.top + yFor(v, scale, plotH)
  const base = y(0)
  /** The translated 'Profit {amount}' / 'Loss {amount}' with the amount taken out, leaving just the word. */
  const profitWord = (profit: number) => t(profit < 0 ? 'chart.loss' : 'chart.profit', { amount: '\u0001' }).replace('\u0001', '').trim()

  return (
    <figure className="chart">
      <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={caption} className="chart-svg" style={{ minWidth: Math.round(W * 0.8) }}>
        {scale.ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className={t === 0 ? 'chart-axis' : 'chart-grid'} />
            <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end" className="chart-tick">
              {formatLakh(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => (
          <g key={d.label}>
            <g>
              <title>{t('chart.revenueTitle', { label: d.label, amount: formatMoney(d.revenue) })}</title>
              <rect x={cx(i) - group / 2} y={y(d.revenue)} width={barW} height={Math.max(base - y(d.revenue), 0)} rx={4} className="chart-bar is-revenue" />
              {d.revenue > 0 && (
                <text x={cx(i) - group / 2 + barW / 2} y={y(d.revenue) - 9} textAnchor="middle" className="chart-value">
                  {formatLakh(d.revenue)}
                </text>
              )}
            </g>
            <g>
              <title>{t('chart.costTitle', { label: d.label, amount: formatMoney(d.cost) })}</title>
              <rect x={cx(i) + 7} y={y(d.cost)} width={barW} height={Math.max(base - y(d.cost), 0)} rx={4} className="chart-bar is-cost" />
              {d.cost > 0 && (
                <text x={cx(i) + 7 + barW / 2} y={y(d.cost) - 9} textAnchor="middle" className="chart-value">
                  {formatLakh(d.cost)}
                </text>
              )}
            </g>
            <text textAnchor="middle" className={d.profit < 0 ? 'chart-profit is-loss' : 'chart-profit'}>
              <tspan x={cx(i)} y={16}>
                {profitWord(d.profit)}
              </tspan>
              <tspan x={cx(i)} y={34}>
                {formatLakh(Math.abs(d.profit))}
              </tspan>
            </text>
            <text x={cx(i)} y={H - 10} textAnchor="middle" className="chart-tick">
              {d.label}
            </text>
          </g>
        ))}
      </svg>
      </div>
      <figcaption className="chart-legend">
        <span>
          <i className="chart-key is-revenue" aria-hidden /> {t('chart.revenue')}
        </span>
        <span>
          <i className="chart-key is-cost" aria-hidden /> {t('chart.cost')}
        </span>
        <span className="muted">{t('chart.note')}</span>
      </figcaption>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th>{t('qc.col.order')}</th>
            <th>{t('chart.revenue')}</th>
            <th>{t('chart.cost')}</th>
            <th>{t('chart.profitWord')}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <td>{d.label}</td>
              <td>{d.revenue}</td>
              <td>{d.cost}</td>
              <td>{d.profit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
