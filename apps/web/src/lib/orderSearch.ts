import type { components } from '@/lib/api'

type Order = components['schemas']['OrderOut']

/** Whether the order matches what was typed: its code, buyer, fabric, colour or stage, every word of it. */
export function matchesSearch(o: Order, query: string): boolean {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const text = [o.code, o.buyer.name, o.fabric_type.name, o.colour, o.stage.replace(/_/g, ' '), o.state].join(' ').toLowerCase()
  return words.every((w) => text.includes(w))
}
