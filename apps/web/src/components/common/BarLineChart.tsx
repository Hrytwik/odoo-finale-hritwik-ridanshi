import { niceScale, yFor } from '@/lib/chart'
import { formatLakh } from '@/lib/format'

export type ChartPoint = { label: string; bar: number; line: number }

const W = 640
const H = 280
const PAD = { top: 16, right: 16, bottom: 36, left: 64 }

/**
 * Bars and a line on the same rupee axis: here revenue as bars and profit as the line, one pair per order.
 * Drawn as plain SVG so it needs no library, follows the light and dark colours, and has a table for screen readers.
 */
export function BarLineChart({ data, barLabel, lineLabel, caption }: { data: ChartPoint[]; barLabel: string; lineLabel: string; caption: string }) {
  const scale = niceScale(data.flatMap((d) => [d.bar, d.line]))
  const plotW = W - PAD.left - PAD.right
  const plotH = H - PAD.top - PAD.bottom
  const band = plotW / Math.max(data.length, 1)
  const barW = Math.min(band * 0.5, 56)
  const x = (i: number) => PAD.left + band * i + band / 2
  const y = (v: number) => PAD.top + yFor(v, scale, plotH)
  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(d.line)}`).join(' ')
  const zero = y(0)
  const areaPath = data.length > 1 ? `${linePath} L${x(data.length - 1)},${zero} L${x(0)},${zero} Z` : ''
  const last = data.at(-1)

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={caption} className="chart-svg">
        <defs>
          <linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" className="chart-fill-top" />
            <stop offset="1" className="chart-fill-bottom" />
          </linearGradient>
        </defs>
        {scale.ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className={t === 0 ? 'chart-axis' : 'chart-grid'} />
            <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end" className="chart-tick">
              {formatLakh(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const top = Math.min(y(d.bar), zero)
          return <rect key={d.label} x={x(i) - barW / 2} y={top} width={barW} height={Math.abs(zero - y(d.bar))} rx={3} className="chart-bar" />
        })}
        {areaPath && <path d={areaPath} fill="url(#chart-fill)" />}
        {data.length > 1 && <path d={linePath} className="chart-line" fill="none" />}
        {data.map((d, i) => (
          <circle key={d.label} cx={x(i)} cy={y(d.line)} r={i === data.length - 1 ? 5 : 3.5} className={i === data.length - 1 ? 'chart-dot is-last' : 'chart-dot'} />
        ))}
        {data.map((d, i) => (
          <text key={d.label} x={x(i)} y={H - 12} textAnchor="middle" className="chart-tick">
            {d.label}
          </text>
        ))}
      </svg>
      <figcaption className="chart-legend">
        <span>
          <i className="chart-key-bar" aria-hidden /> {barLabel}
        </span>
        <span>
          <i className="chart-key-line" aria-hidden /> {lineLabel}
        </span>
        {last && (
          <span className="muted">
            Latest: {last.label} {formatLakh(last.line)}
          </span>
        )}
      </figcaption>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th>Order</th>
            <th>{barLabel}</th>
            <th>{lineLabel}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <td>{d.label}</td>
              <td>{d.bar}</td>
              <td>{d.line}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
