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
import { api, call, errorMessage, type components } from '@/lib/api'
import { generatePassword, LOGIN_ROLE_FOR_JOB, slipHtml, suggestUsername } from '@/lib/credentials'
import { useSubmitLock } from '@/lib/forms'
import { ROLE_LABEL } from '@/lib/nav'

type Worker = components['schemas']['WorkerOut']
type User = components['schemas']['UserOut']

/** On a worker's row: their login if they have one, a "Create login" button if their job needs one, nothing for operators and helpers. */
export function WorkerLoginCell({ worker }: { worker: Worker }) {
  const users = useQuery({ queryKey: ['master', 'users'], queryFn: () => call(api.GET('/api/users')) })
  const [open, setOpen] = useState(false)
  const role = LOGIN_ROLE_FOR_JOB[worker.role]
  const existing = users.data?.find((u) => u.worker_id === worker.id)
  if (existing) return <Badge tone="green">Login: {existing.username}</Badge>
  if (!role || !worker.active || !users.data) return <span className="muted text-sm">{role ? '' : 'No login needed'}</span>
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)} aria-label={`Create a login for ${worker.name}`}>
        <KeyRound size={14} aria-hidden /> Create login
      </Button>
      {open && <CreateLoginDialog worker={worker} role={role} users={users.data} onClose={() => setOpen(false)} />}
    </>
  )
}

function CreateLoginDialog({ worker, role, users, onClose }: { worker: Worker; role: 'qc' | 'store' | 'supervisor' | 'dispatch'; users: User[]; onClose: () => void }) {
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
      await navigator.clipboard.writeText(`Username: ${username}\nPassword: ${password}`)
      toast.success('Copied')
    } catch {
      toast.error('Could not copy. Select the text and copy it by hand.')
    }
  }

  function printSlip() {
    const w = window.open('', '_blank', 'width=520,height=640')
    if (!w) return toast.error('The slip window was blocked. Allow pop-ups for this site, or copy the details instead.')
    w.document.write(slipHtml(worker.name, username, password, window.location.origin))
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <Dialog open onClose={onClose} title={created ? `Login created for ${worker.name}` : `Create a login for ${worker.name}`}>
      {created ? (
        <div className="stack">
          <Alert tone="info">This password is shown only now. Copy it or print the slip, and give it to {worker.name}. They can change it after logging in.</Alert>
          <dl className="credential-box">
            <dt>Username</dt>
            <dd>{username}</dd>
            <dt>Temporary password</dt>
            <dd>{password}</dd>
          </dl>
          <div className="row">
            <Button variant="secondary" onClick={() => void copy()}>
              <Copy size={16} aria-hidden /> Copy
            </Button>
            <Button variant="secondary" onClick={printSlip}>
              <Printer size={16} aria-hidden /> Print slip
            </Button>
            <Button onClick={onClose}>Done</Button>
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
            {worker.name} will log in as <strong>{ROLE_LABEL[role]}</strong>, linked to their worker record. Change the username if you like.
          </p>
          <Field label="Username">{(c) => <Input {...c} autoComplete="off" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} />}</Field>
          <Field label="Temporary password" hint="Random and strong. Make a new one if you prefer.">
            {(c) => (
              <span className="row">
                <Input {...c} readOnly value={password} />
                <Button variant="secondary" icon aria-label="Make a new password" onClick={() => setPassword(generatePassword())}>
                  <RefreshCw size={16} aria-hidden />
                </Button>
              </span>
            )}
          </Field>
          {error && <Alert tone="error">{error}</Alert>}
          <div className="row">
            <SubmitButton pending={pending}>Create login</SubmitButton>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
