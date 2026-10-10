import { BellRing } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ActionDialog } from '@/components/common/ActionDialog'
import { Button } from '@/components/ui/Button'
import { Field, Select, Textarea } from '@/components/ui/Field'
import { api, call, errorMessage } from '@/lib/api'
import { useMe } from '@/lib/auth'
import { useSubmitLock } from '@/lib/forms'

/** The reasons the owner can pick from. The same list, in the same order, as the server's. */
const DELAY_REASONS = [
  { value: 'yarn_shortage', label: 'Yarn shortage' },
  { value: 'machine_breakdown', label: 'Machine breakdown' },
  { value: 'power_cut', label: 'Power cut' },
  { value: 'staff_shortage', label: 'Staff shortage' },
  { value: 'quality_rework', label: 'Quality rework' },
  { value: 'dye_delay', label: 'Dye or chemical delay' },
  { value: 'transport', label: 'Transport problem' },
  { value: 'buyer_change', label: 'Change to the order' },
  { value: 'other', label: 'Other' },
] as const
type Reason = (typeof DELAY_REASONS)[number]['value']

/** "Tell the buyer about a delay": the owner picks one reason, a sentence is drafted, the owner can edit it, then it goes to the buyer's bell. */
export function DelayNoticeButton({ orderCode, buyerName }: { orderCode: string; buyerName: string }) {
  const me = useMe()
  const [open, setOpen] = useState(false)
  if (me.data?.role !== 'owner') return null
  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <BellRing size={16} aria-hidden /> Tell the buyer about a delay
      </Button>
      {open && <DelayNoticeDialog orderCode={orderCode} buyerName={buyerName} onClose={() => setOpen(false)} />}
    </>
  )
}

function DelayNoticeDialog({ orderCode, buyerName, onClose }: { orderCode: string; buyerName: string; onClose: () => void }) {
  const path = { params: { path: { order_code: orderCode } } }
  const [reason, setReason] = useState<Reason | ''>('')
  const [message, setMessage] = useState('')
  const [byModel, setByModel] = useState<boolean | null>(null)
  const [drafting, setDrafting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { run, pending } = useSubmitLock()

  async function choose(next: Reason | '') {
    setReason(next)
    setMessage('')
    setByModel(null)
    setError(null)
    if (!next) return
    setDrafting(true)
    try {
      const d = await call(api.POST('/api/orders/{order_code}/delay-notice/draft', { ...path, body: { reason: next } }))
      setMessage(d.message)
      setByModel(d.drafted_by_ai)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setDrafting(false)
    }
  }

  const send = () =>
    run(async () => {
      if (!reason) return setError('Choose a reason first')
      if (!message.trim()) return setError('The message cannot be empty')
      setError(null)
      try {
        await call(api.POST('/api/orders/{order_code}/delay-notice', { ...path, body: { reason, message } }))
        toast.success(`${buyerName} has been told`)
        onClose()
      } catch (err) {
        setError(errorMessage(err))
      }
    })

  return (
    <ActionDialog open onClose={onClose} title={`Tell ${buyerName} about a delay`} confirmLabel="Send to the buyer" onConfirm={() => void send()} pending={pending} error={error}>
      <p className="muted text-sm">
        Choose the reason. A short message is written for you to read and change. The buyer sees it as a notification on {orderCode}.
      </p>
      <Field label="Reason for the delay">
        {(c) => (
          <Select {...c} value={reason} onChange={(e) => void choose(e.target.value as Reason | '')}>
            <option value="">Choose a reason</option>
            {DELAY_REASONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      {drafting && (
        <p className="muted text-sm" role="status">
          <span className="spinner" aria-hidden /> Writing the messageâ€¦
        </p>
      )}
      {reason && !drafting && byModel !== null && (
        <Field label="Message to the buyer" hint={byModel ? 'Written by the AI. Read it, and change anything you like, before you send.' : 'A standard message. Change anything you like before you send.'}>
          {(c) => <Textarea {...c} rows={4} maxLength={400} value={message} onChange={(e) => setMessage(e.target.value)} />}
        </Field>
      )}
    </ActionDialog>
  )
}
