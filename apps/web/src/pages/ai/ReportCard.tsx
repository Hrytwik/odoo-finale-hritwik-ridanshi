import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Play, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useI18n } from '@/i18n/I18nContext'
import { formatDateTime } from '@/lib/format'
import { useSubmitLock } from '@/lib/forms'

type Run = components['schemas']['ReportCardOut']

/** Asks the configured model questions whose right answers are read from the data just now, and marks it. */
export default function ReportCard() {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const runs = useQuery({ queryKey: ['ai', 'report-card'], queryFn: () => call(api.GET('/api/ai/report-card')) })
  const { run, pending } = useSubmitLock()
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)

  const start = () =>
    run(async () => {
      setError(null)
      try {
        const card = await call(api.POST('/api/ai/report-card/run'))
        setOpenId(card.id)
        await queryClient.invalidateQueries({ queryKey: ['ai', 'report-card'] })
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  return (
    <>
      <PageHeader
        eyebrow="AI"
        title={t('rc.title')}
        description={t('rc.description')}
        actions={
          <>
            <Link to="/settings/ai">
              <Button variant="secondary">{t('nav.aiSettings')}</Button>
            </Link>
            <SubmitButton pending={pending} onClick={() => void start()}>
              <Play size={16} aria-hidden /> {t('rc.run')}
            </SubmitButton>
          </>
        }
      />
      <div className="stack">
        {pending && (
          <Alert tone="info">
            {t('rc.asking')}
          </Alert>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <QueryBoundary query={runs}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title={t('rc.noRuns')} description={t('rc.noRunsHint')} />
            ) : (
              <Reveal>
                <ul className="runs">
                  {list.map((r) => (
                    <li key={r.id}>
                      <button type="button" className={r.id === (openId ?? list[0].id) ? 'run is-open' : 'run'} onClick={() => setOpenId(r.id)}>
                        <span className="run-score">
                          {r.score}/{r.total}
                        </span>
                        <span>
                          <strong>{r.model}</strong>
                          <span className="muted text-sm"> {r.provider} · {formatDateTime(r.run_at)}</span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                <Details run={list.find((r) => r.id === (openId ?? list[0].id)) ?? list[0]} />
              </Reveal>
            )
          }
        </QueryBoundary>
      </div>
    </>
  )
}

function Details({ run }: { run: Run }) {
  const { t } = useI18n()
  const failed = run.details.filter((d) => !d.passed).length
  return (
    <section className="stack-sm" aria-label={t('rc.answersFrom', { model: run.model })}>
      <h2>
        {t('rc.score', { model: run.model, score: run.score, total: run.total })} {failed === 0 ? <Badge tone="green">{t('rc.fullMarks')}</Badge> : <Badge tone="amber">{t('rc.nWrong', { n: failed })}</Badge>}
      </h2>
      <Table>
        <thead>
          <tr>
            <th>{t('rc.col.question')}</th>
            <th>{t('rc.col.expected')}</th>
            <th>{t('rc.col.said')}</th>
            <th>{t('log.result')}</th>
          </tr>
        </thead>
        <tbody>
          {run.details.map((d) => (
            <tr key={d.question}>
              <td>{d.question}</td>
              <td>
                <span className="code-text">{d.expected}</span>
              </td>
              <td className="text-sm">{d.answer}</td>
              <td>
                {d.passed ? (
                  <Badge tone="green">
                    <Check size={12} aria-hidden /> {t('rc.right')}
                  </Badge>
                ) : (
                  <Badge tone="red">
                    <X size={12} aria-hidden /> {t('rc.wrong')}
                  </Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </section>
  )
}
