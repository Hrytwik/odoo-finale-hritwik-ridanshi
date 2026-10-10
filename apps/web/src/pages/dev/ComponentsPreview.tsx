import { useState } from 'react'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingState } from '@/components/common/LoadingState'
import { PageHeader } from '@/components/common/PageHeader'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Badge, type Tone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input, Select, Textarea } from '@/components/ui/Field'
import { Table } from '@/components/ui/Table'
import { formatKg, formatMetres, formatMoney } from '@/lib/format'

const TONES: Tone[] = ['green', 'amber', 'red', 'blue', 'violet', 'gray']

/** Dev-only page that shows every shared component. Useful when restyling `styles/theme.css`. */
export default function ComponentsPreview() {
  const [menu, setMenu] = useState(false)
  const [dialog, setDialog] = useState(false)
  const [pending, setPending] = useState(false)

  return (
    <div className="stack">
      <PageHeader
        title="Component preview"
        description="Everything the screens are built from. Colours and spacing come from styles/theme.css."
        actions={
          <>
            <Button variant="secondary" onClick={() => setMenu(true)}>
              Open menu drawer
            </Button>
            <Button onClick={() => setDialog(true)}>Open dialog</Button>
          </>
        }
      />

      <Card title="Buttons">
        <div className="row">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button disabled>Disabled</Button>
          <SubmitButton pending={pending} onClick={() => setPending(true)}>
            {pending ? 'Saving' : 'Save (tap me)'}
          </SubmitButton>
        </div>
      </Card>

      <Card title="Form: receive yarn">
        <form className="stack" onSubmit={(e) => e.preventDefault()} noValidate>
          <div className="grid-cards">
            <Field label="Supplier">
              {(c) => (
                <Select {...c} defaultValue="">
                  <option value="" disabled>
                    Choose a supplier
                  </option>
                  <option>Vardhman Yarns</option>
                </Select>
              )}
            </Field>
            <Field label="Challan number" error="This challan was already entered for this supplier and yarn type">
              {(c) => <Input {...c} defaultValue="CH-5521" />}
            </Field>
            <Field label="Quantity (kg)" hint="Weigh the lot at the gate">
              {(c) => <Input {...c} type="number" inputMode="decimal" />}
            </Field>
          </div>
          <Field label="Note">{(c) => <Textarea {...c} />}</Field>
          <Alert tone="error">Server rejected the form. This is the form-level message.</Alert>
          <Alert>Info message, for example "Stock updates live".</Alert>
        </form>
      </Card>

      <Card title="Status badges">
        <div className="row">
          {TONES.map((t) => (
            <Badge key={t} tone={t}>
              {t}
            </Badge>
          ))}
        </div>
      </Card>

      <Table>
        <thead>
          <tr>
            <th>Order</th>
            <th>Buyer</th>
            <th>Stage</th>
            <th className="num">Metres</th>
            <th className="num">Yarn</th>
            <th className="num">Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>ORD-0012</td>
            <td>Sharma Fabrics</td>
            <td>
              <Badge tone="blue">Weaving</Badge>
            </td>
            <td className="num">{formatMetres(5000)}</td>
            <td className="num">{formatKg(587.5)}</td>
            <td className="num">{formatMoney(600000)}</td>
          </tr>
          <tr>
            <td>ORD-0015</td>
            <td>Patel Textiles</td>
            <td>
              <Badge tone="amber">Waiting to start</Badge>
            </td>
            <td className="num">{formatMetres(1200)}</td>
            <td className="num">{formatKg(144)}</td>
            <td className="num">{formatMoney(150000)}</td>
          </tr>
        </tbody>
      </Table>

      <div className="grid-cards">
        <LoadingState rows={2} />
        <EmptyState title="No orders yet" description="Create the first one to see it here." />
        <ErrorState error={new Error('x')} onRetry={() => undefined} />
      </div>

      <Dialog open={menu} onClose={() => setMenu(false)} title="Menu" side="left">
        <nav className="stack-sm">
          <a href="#orders">Orders</a>
          <a href="#floor">Floor board</a>
          <a href="#qc">Quality check</a>
        </nav>
      </Dialog>
      <Dialog open={dialog} onClose={() => setDialog(false)} title="Confirm dispatch">
        <div className="stack">
          <p>6 rolls, 660 m for Sharma Fabrics. This creates the invoice and cannot be undone.</p>
          <div className="row">
            <Button onClick={() => setDialog(false)}>Confirm</Button>
            <Button variant="secondary" onClick={() => setDialog(false)}>
              Cancel
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
