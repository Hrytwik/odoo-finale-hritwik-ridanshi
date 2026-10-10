import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, MessageCircle, Send } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { ApiError, api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

type Settings = components['schemas']['MessagingSettingsOut']

/** Connects the mill to WhatsApp through a Twilio account, so a delay notice also reaches the buyer's phone. */
export default function WhatsAppSettings() {
  const settings = useQuery({ queryKey: ['messaging', 'settings'], queryFn: () => call(api.GET('/api/messaging/settings')) })
  return (
    <>
      <PageHeader
        eyebrow="AI and messages"
        title="WhatsApp"
        description="Connect a Twilio WhatsApp account so a delay notice reaches the buyer on WhatsApp as well as in their notification bell. The mill works the same without it."
      />
      <QueryBoundary query={settings}>{(s) => <Connection key={`${s.account_sid}-${s.token_set}-${s.from_number}-${s.content_sid}-${s.public_url}-${s.enabled}`} current={s} />}</QueryBoundary>
    </>
  )
}

function Connection({ current }: { current: Settings }) {
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [sid, setSid] = useState(current.account_sid ?? '')
  const [token, setToken] = useState('')
  const [from, setFrom] = useState(current.from_number ?? '')
  const [contentSid, setContentSid] = useState(current.content_sid ?? '')
  const [url, setUrl] = useState(current.public_url ?? window.location.origin)
  const [enabled, setEnabled] = useState(current.enabled)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const save = () =>
    run(async () => {
      setErrors({})
      setFormError(null)
      try {
        await call(
          api.PUT('/api/messaging/settings', {
            // an empty token box means "keep the saved one"
            body: { account_sid: sid.trim(), from_number: from.trim(), content_sid: contentSid.trim(), public_url: url.trim(), enabled, ...(token.trim() ? { auth_token: token.trim() } : {}) },
          }),
        )
        toast.success('WhatsApp settings saved')
        setToken('')
        await queryClient.invalidateQueries({ queryKey: ['messaging'] })
      } catch (err) {
        if (err instanceof ApiError && err.field) setErrors({ [err.field]: err.body.message })
        else setFormError(errorMessage(err))
      }
    })

  return (
    <div className="stack">
      <p className="row">
        {current.ready ? <Badge tone="green">Connected</Badge> : <Badge tone="amber">Not connected</Badge>}
        <span className="muted text-sm">{current.ready ? 'Delay notices are also sent on WhatsApp.' : 'Fill in the details below and switch it on.'}</span>
      </p>

      <section className="card" aria-label="How to connect">
        <div className="card-body stack-sm">
          <h2 className="card-title">Connect in five minutes (Twilio WhatsApp sandbox)</h2>
          <ol className="steps">
            <li>Create a free account at twilio.com and open <strong>Messaging, Try it out, Send a WhatsApp message</strong>.</li>
            <li>On each phone that should receive messages, send the <strong>join code</strong> shown there to the sandbox number, once.</li>
            <li>Copy the <strong>Account SID</strong> and the <strong>Auth Token</strong> from your Twilio dashboard and paste them below. The token is stored encrypted and is never shown again.</li>
            <li>Enter the sandbox number as the sender. If Twilio answers "ContentSid Required" (error 21654), make a message template (next section) and paste its ID.</li>
            <li>Switch it on, save, and send yourself a test message.</li>
            <li>Make sure each buyer has their phone number under <strong>Buyers</strong>.</li>
          </ol>
        </div>
      </section>

      <form
        className="card"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void save()
        }}
      >
        <div className="card-body stack">
          <Field label="Account SID" error={errors.account_sid}>
            {(c) => <Input {...c} autoComplete="off" autoCapitalize="none" placeholder="AC..." value={sid} onChange={(e) => setSid(e.target.value)} />}
          </Field>
          <Field label="Auth Token" error={errors.auth_token} hint={current.token_set ? 'A token is saved. Leave this empty to keep it.' : 'Stored encrypted and never shown again.'}>
            {(c) => <Input {...c} type="password" autoComplete="new-password" placeholder={current.token_set ? 'Saved' : ''} value={token} onChange={(e) => setToken(e.target.value)} />}
          </Field>
          <Field label="WhatsApp sender number" error={errors.from_number} hint="The sandbox number from Twilio, for example +14155238886.">
            {(c) => <Input {...c} autoComplete="off" value={from} onChange={(e) => setFrom(e.target.value)} />}
          </Field>
          <Field
            label="Message template ID (only if Twilio asks for one)"
            error={errors.content_sid}
            hint="Starts with HX. In Twilio: Content Template Builder, create a Text template named everest_update, language English, with this body, and copy its Content SID."
          >
            {(c) => <Input {...c} autoComplete="off" autoCapitalize="none" placeholder="HX..." value={contentSid} onChange={(e) => setContentSid(e.target.value)} />}
          </Field>
          <pre className="template-sample" aria-label="Template body to create in Twilio">Everest Mills update: {'{{1}}'} Track your order: {'{{2}}'}</pre>
          <Field label="Address buyers use to follow their order" error={errors.public_url} hint="Put in the message as the tracking link. Use the address buyers can reach, for example your HTTPS address.">
            {(c) => <Input {...c} autoComplete="off" autoCapitalize="none" value={url} onChange={(e) => setUrl(e.target.value)} />}
          </Field>
          <label className="check-row">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Send delay notices on WhatsApp
          </label>
          {errors.enabled && <Alert tone="error">{errors.enabled}</Alert>}
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="row">
            <SubmitButton pending={pending}>Save settings</SubmitButton>
          </div>
        </div>
      </form>

      <TestMessage disabled={!current.ready} />
    </div>
  )
}

function TestMessage({ disabled }: { disabled: boolean }) {
  const { run, pending } = useSubmitLock()
  const [to, setTo] = useState('')
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null)
  const send = () =>
    run(async () => {
      setResult(null)
      try {
        const r = await call(api.POST('/api/messaging/test', { body: { to } }))
        setResult(r.status === 'sent' ? { ok: true, text: `Sent to ${r.to}. Check that phone's WhatsApp.` } : { ok: false, text: r.detail ?? 'It was not sent.' })
      } catch (err) {
        setResult({ ok: false, text: errorMessage(err) })
      }
    })
  return (
    <section className="card" aria-label="Send a test message">
      <div className="card-body stack-sm">
        <h2 className="card-title">Send a test message</h2>
        <p className="muted text-sm">Sends one short message to a phone that has joined the sandbox. Save your details first.</p>
        <Field label="Phone number">
          {(c) => <Input {...c} type="tel" autoComplete="off" placeholder="+91 98450 12345" value={to} onChange={(e) => setTo(e.target.value)} />}
        </Field>
        <div className="row">
          <Button variant="secondary" onClick={() => void send()} disabled={disabled || pending || !to.trim()}>
            {pending ? <span className="spinner" aria-hidden /> : <Send size={16} aria-hidden />} Send a test message
          </Button>
          {disabled && <span className="muted text-sm">Connect and save first.</span>}
        </div>
        {result &&
          (result.ok ? (
            <p role="status" className="row">
              <CheckCircle2 size={16} aria-hidden /> {result.text}
            </p>
          ) : (
            <Alert tone="error">{result.text}</Alert>
          ))}
        <p className="muted text-sm row">
          <MessageCircle size={14} aria-hidden /> The sandbox sends only to phones that joined it.
        </p>
      </div>
    </section>
  )
}
