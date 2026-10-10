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
import { formatDateTime } from '@/lib/format'
import { useSubmitLock } from '@/lib/forms'

type Run = components['schemas']['ReportCardOut']

/** Asks the configured model questions whose right answers are read from the data just now, and marks it. */
export default function ReportCard() {
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
        title="Report card"
        description="The model answers questions about the mill's current numbers. An answer passes when it contains the figure the mill's own calculations give."
        actions={
          <>
            <Link to="/settings/ai">
              <Button variant="secondary">AI settings</Button>
            </Link>
            <SubmitButton pending={pending} onClick={() => void start()}>
              <Play size={16} aria-hidden /> Run the report card
            </SubmitButton>
          </>
        }
      />
      <div className="stack">
        {pending && (
          <Alert tone="info">
            Asking the model each question. This can take a minute.
          </Alert>
        )}
        {error && <Alert tone="error">{error}</Alert>}
        <QueryBoundary query={runs}>
          {(list) =>
            list.length === 0 ? (
              <EmptyState title="No runs yet" description="Run the report card to see how the chosen model does on questions about your own data." />
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
  const failed = run.details.filter((d) => !d.passed).length
  return (
    <section className="stack-sm" aria-label={`Answers from ${run.model}`}>
      <h2>
        {run.model}: {run.score} of {run.total} right {failed === 0 ? <Badge tone="green">Full marks</Badge> : <Badge tone="amber">{failed} wrong</Badge>}
      </h2>
      <Table>
        <thead>
          <tr>
            <th>Question</th>
            <th>The right figure</th>
            <th>The model said</th>
            <th>Result</th>
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
                    <Check size={12} aria-hidden /> Right
                  </Badge>
                ) : (
                  <Badge tone="red">
                    <X size={12} aria-hidden /> Wrong
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
