import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import type { DefectType } from '@/lib/defects'

/** The name of a defect type in the chosen language. */
export function useDefectLabel() {
  const { t } = useI18n()
  return (type: DefectType) => t(`defect.${type}` as Key)
}
