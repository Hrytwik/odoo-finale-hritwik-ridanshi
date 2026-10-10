import { useState } from 'react'
import { PageHeader } from '@/components/common/PageHeader'
import { useI18n } from '@/i18n/I18nContext'
import { ModelAccuracy } from './ModelCard'
import { PhotoLog } from './PhotoLog'

/** The Vision model page: the log of every checked photo, and how accurate the model has been. Open to the owner and the inspector. */
export default function VisionModel() {
  const { t } = useI18n()
  const [tab, setTab] = useState<'log' | 'model'>('log')
  return (
    <>
      <PageHeader title={t('nav.visionModel')} description={t('vision.description')} />
      <div className="tabs" role="tablist" aria-label={t('nav.visionModel')}>
        {(['log', 'model'] as const).map((k) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? 'tab is-on' : 'tab'} onClick={() => setTab(k)}>
            {t(k === 'log' ? 'vision.tab.log' : 'vision.tab.model')}
          </button>
        ))}
      </div>
      {tab === 'log' ? <PhotoLog /> : <ModelAccuracy />}
    </>
  )
}
