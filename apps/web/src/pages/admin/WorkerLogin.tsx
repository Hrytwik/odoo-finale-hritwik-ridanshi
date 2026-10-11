import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, Printer, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input } from '@/components/ui/Field'
import type { Key } from '@/i18n/en'
import { useI18n } from '@/i18n/I18nContext'
import { api, call, errorMessage, type components } from '@/lib/api'
import { generatePassword, LOGIN_ROLE_FOR_JOB, slipHtml, suggestUsername } from '@/lib/credentials'
import { useSubmitLock } from '@/lib/forms'

type Worker = components['schemas']['WorkerOut']
type User = components['schemas']['UserOut']

/** On a worker's row: their login if they have one, a "Create login" button if their job needs one, nothing for operators and helpers. */
export function WorkerLoginCell({ worker }: { worker: Worker }) {
  const { t } = useI18n()
  const users = useQuery({ queryKey: ['master', 'users'], queryFn: () => call(api.GET('/api/users')) })
  const [open, setOpen] = useState(false)
  const role = LOGIN_ROLE_FOR_JOB[worker.role]
  const existing = users.data?.find((u) => u.worker_id === worker.id)
  if (existing) return <Badge tone="green">{t('wl.loginBadge', { name: existing.username })}</Badge>
  if (!role || !worker.active || !users.data) return <span className="muted text-sm">{role ? '' : t('wl.noLoginNeeded')}</span>
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)} aria-label={t('wl.createFor', { name: worker.name })}>
        <KeyRound size={14} aria-hidden /> {t('wl.create')}
      </Button>
      {open && <CreateLoginDialog worker={worker} role={role} users={users.data} onClose={() => setOpen(false)} />}
    </>
  )
}

function CreateLoginDialog({ worker, role, users, onClose }: { worker: Worker; role: 'qc' | 'store' | 'supervisor' | 'dispatch'; users: User[]; onClose: () => void }) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [username, setUsername] = useState(() => suggestUsername(worker.name, new Set(users.map((u) => u.username))))
  const [password, setPassword] = useState(() => generatePassword())
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState(false)

  const create = () =>
    run(async () => {
      setError(null)
      try {
        await call(api.POST('/api/users', { body: { username: username.trim(), password, role, worker_id: worker.id } }))
        setCreated(true)
        void queryClient.invalidateQueries({ queryKey: ['master', 'users'] })
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  async function copy() {
    try {
      await navigator.clipboard.writeText(t('wl.copyFormat', { username, password }))
      toast.success(t('draft.copied'))
    } catch {
      toast.error(t('draft.copyFailed'))
    }
  }

  function printSlip() {
    const w = window.open('', '_blank', 'width=520,height=640')
    if (!w) return toast.error(t('wl.popupBlocked'))
    w.document.write(
      slipHtml(worker.name, username, password, window.location.origin, {
        brand: t('brand.name'),
        loginFor: (n) => t('slip.loginFor', { name: n }),
        address: t('slip.address'),
        username: t('admin.col.username'),
        password: t('wl.tempPassword'),
        changeAfter: t('slip.changeAfter'),
      }),
    )
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <Dialog open onClose={onClose} title={created ? t('wl.created', { name: worker.name }) : t('wl.createFor', { name: worker.name })}>
      {created ? (
        <div className="stack">
          <Alert tone="info">{t('wl.shownOnce', { name: worker.name })}</Alert>
          <dl className="credential-box">
            <dt>{t('admin.col.username')}</dt>
            <dd>{username}</dd>
            <dt>{t('wl.tempPassword')}</dt>
            <dd>{password}</dd>
          </dl>
          <div className="row">
            <Button variant="secondary" onClick={() => void copy()}>
              <Copy size={16} aria-hidden /> {t('draft.copy')}
            </Button>
            <Button variant="secondary" onClick={printSlip}>
              <Printer size={16} aria-hidden /> {t('wl.printSlip')}
            </Button>
            <Button onClick={onClose}>{t('wl.done')}</Button>
          </div>
        </div>
      ) : (
        <form
          className="stack"
          noValidate
          onSubmit={(e) => {
            e.preventDefault()
            void create()
          }}
        >
          <p className="muted text-sm">
            {(() => {
              // the role is shown in bold, wherever the language puts it in the sentence
              const [before, after] = t('wl.willLogInAs', { name: worker.name, role: '' }).split('')
              return (
                <>
                  {before}
                  <strong>{t(`role.${role}` as Key)}</strong>
                  {after}
                </>
              )
            })()}
          </p>
          <Field label={t('admin.col.username')}>{(c) => <Input {...c} autoComplete="off" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} />}</Field>
          <Field label={t('wl.tempPassword')} hint={t('wl.tempPasswordHint')}>
            {(c) => (
              <span className="row">
                <Input {...c} readOnly value={password} />
                <Button variant="secondary" icon aria-label={t('wl.newPassword')} onClick={() => setPassword(generatePassword())}>
                  <RefreshCw size={16} aria-hidden />
                </Button>
              </span>
            )}
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row">
            <SubmitButton pending={pending}>{t('wl.create')}</SubmitButton>
            <Button variant="secondary" onClick={onClose}>
              {t('dispatch.cancel')}
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
