import type { components } from '@/lib/api'
import { useDefectLabel } from '@/lib/useDefectLabel'

type Box = components['schemas']['Box']


/** A 0 to 1 fraction as a CSS percentage, rounded to 2 decimals (so 0.07 is "7%", not "7.000000000000001%"). */
const pct = (fraction: number) => `${Math.round(fraction * 10000) / 100}%`

/** A photo with the model's suggested defects drawn over it. Box positions are 0 to 1 fractions of the photo, so they scale with it. */
export function PhotoWithBoxes({ src, boxes, alt }: { src: string; boxes: Box[]; alt: string }) {
  const label = useDefectLabel()
  return (
    <div className="photo-wrap">
      <img src={src} alt={alt} />
      {boxes.map((b, i) => (
        <div
          key={i}
          data-testid={`box-${i}`}
          className="photo-box"
          style={{ left: pct(b.x), top: pct(b.y), width: pct(b.w), height: pct(b.h) }}
        >
          <span className="photo-box-label">
            {label(b.defect_type)} {Math.round(b.confidence * 100)}%
          </span>
        </div>
      ))}
    </div>
  )
}
