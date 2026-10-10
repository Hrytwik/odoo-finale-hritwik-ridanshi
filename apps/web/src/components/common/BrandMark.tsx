/** A tiny square of plain weave: threads going over and under. Used as the logo mark. */
export function BrandMark({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" aria-hidden="true">
      {/* three horizontal threads */}
      <g fill="#fff">
        <rect x="0" y="1" width="18" height="4" rx="2" />
        <rect x="0" y="7" width="18" height="4" rx="2" />
        <rect x="0" y="13" width="18" height="4" rx="2" />
      </g>
      {/* three vertical threads crossing over the first and third, under the second */}
      <g fill="#f4b942">
        <rect x="1" y="0" width="4" height="7" rx="2" opacity="0.95" />
        <rect x="1" y="11" width="4" height="7" rx="2" opacity="0.95" />
        <rect x="7" y="4" width="4" height="9" rx="2" opacity="0.95" />
        <rect x="13" y="0" width="4" height="7" rx="2" opacity="0.95" />
        <rect x="13" y="11" width="4" height="7" rx="2" opacity="0.95" />
      </g>
    </svg>
  )
}
