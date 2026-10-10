/** A tidy axis for a chart: round tick values that cover every number, so the grid lines read as 0, 50,000, 1,00,000 rather than odd fractions. */
export function niceScale(values: number[], wanted = 4): { min: number; max: number; ticks: number[] } {
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  const span = hi - lo || 1
  const raw = span / wanted
  const pow = 10 ** Math.floor(Math.log10(raw))
  const step = ([1, 2, 5, 10].find((m) => m * pow >= raw) ?? 10) * pow
  const min = Math.floor(lo / step) * step
  const max = Math.ceil(hi / step) * step
  const ticks: number[] = []
  // rounding to the step avoids 0.30000000000000004 style ticks
  for (let t = min; t <= max + step / 2; t += step) ticks.push(Math.round(t / step) * step)
  return { min, max: max === min ? min + step : max, ticks }
}

/** Where a value sits on the vertical axis, in pixels from the top of the plot area. */
export function yFor(value: number, scale: { min: number; max: number }, height: number): number {
  return height - ((value - scale.min) / (scale.max - scale.min)) * height
}
