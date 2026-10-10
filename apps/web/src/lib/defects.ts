import type { components } from '@/lib/api'

export type DefectType = components['schemas']['DefectIn']['defect_type']

/** The words used for each defect type on every screen. Exhaustive: the build fails if the backend adds a type. */
export const DEFECT_LABEL: Record<DefectType, string> = {
  hole: 'Hole',
  stain: 'Stain',
  thread_fault: 'Thread fault',
  colour_mismatch: 'Colour mismatch',
  other: 'Other',
}
