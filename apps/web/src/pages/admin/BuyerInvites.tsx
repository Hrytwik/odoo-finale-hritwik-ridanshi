import { useQuery } from '@tanstack/react-query'
import { Copy } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Filtered } from '@/components/common/ListToolbar'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { Reveal } from '@/components/motion/Reveal'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { useI18n } from '@/i18n/I18nContext'
import { api, call } from '@/lib/api'

async function copy(text: string, done: string, failed: string) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(done)
  } catch {
    toast.error(failed)
  }
}

/** For the owner: what to hand each buyer so they can create their own login. */
export default function BuyerInvites() {
  const { t } = useI18n()
  const invites = useQuery({ queryKey: ['master', 'buyer-invites'], queryFn: () => call(api.GET('/api/auth/buyer-invites')) })
  const signupLink = `${window.location.origin}/signup`
  return (
    <>
      <PageHeader
        eyebrow={t('nav.group.Master data')}
        title={t('nav.buyerInvites')}
        description={t('invites.description')}
        actions={
          <Button variant="secondary" onClick={() => void copy(signupLink, t('invites.copiedWhat', { what: t('invites.linkWhat') }), t('draft.copyFailed'))}>
            <Copy size={16} aria-hidden /> {t('invites.copyLink')}
          </Button>
        }
      />
      <QueryBoundary query={invites}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title={t('invites.emptyTitle')} description={t('invites.emptyDescription')} />
          ) : (
            <Reveal>
              <Filtered
                rows={rows}
                options={{
                  text: (r) => `${r.buyer_name} ${r.email ?? ''} ${r.invite_code ?? ''}`,
                  sorts: [{ key: 'buyer', label: t('qc.col.buyer'), value: (r) => r.buyer_name }],
                  filters: [
                    {
                      key: 'login',
                      label: t('invites.col.login'),
                      options: [
                        { value: 'yes', label: t('invites.hasLogin') },
                        { value: 'no', label: t('invites.notSignedUp') },
                      ],
                      test: (r, v) => (v === 'yes') === r.has_account,
                    },
                  ],
                }}
              >
                {(shown) => (
              <Table>
                <thead>
                  <tr>
                    <th>{t('qc.col.buyer')}</th>
                    <th>{t('invites.col.emailOnRecord')}</th>
                    <th>{t('invites.col.login')}</th>
                    <th>{t('invites.codeWhat')}</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <tr key={r.buyer_id}>
                      <td>{r.buyer_name}</td>
                      <td>{r.email ?? <span className="muted">{t('invites.none')}</span>}</td>
                      <td>{r.has_account ? <Badge tone="green">{t('invites.hasLogin')}</Badge> : <Badge tone="amber">{t('invites.notSignedUp')}</Badge>}</td>
                      <td>
                        {r.invite_code ? (
                          <span className="row">
                            <span className="code-text">{r.invite_code}</span>
                            <Button variant="ghost" icon aria-label={t('invites.copyCodeFor', { name: r.buyer_name })} onClick={() => void copy(r.invite_code as string, t('invites.copiedWhat', { what: t('invites.codeWhat') }), t('draft.copyFailed'))}>
                              <Copy size={16} aria-hidden />
                            </Button>
                          </span>
                        ) : (
                          <span className="muted text-sm">
                            {(() => {
                              const [before, after] = t('invites.addEmailIn', { link: '' }).split('')
                              return (
                                <>
                                  {before}
                                  <Link to="/admin/buyers">{t('nav.buyers')}</Link>
                                  {after}
                                </>
                              )
                            })()}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
                )}
              </Filtered>
            </Reveal>
          )
        }
      </QueryBoundary>
    </>
  )
}
