/** A hash of threads: two warp and two weft crossing, like a swatch seen from above. The logo mark. */
export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M6.5 2 5 16M13 2l-1.5 14M2 6.5h14M1.5 11.5h14" />
    </svg>
  )
}
