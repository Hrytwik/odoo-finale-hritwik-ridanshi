import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/common/PageHeader'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Reveal } from '@/components/motion/Reveal'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Input, Select } from '@/components/ui/Field'
import { Table } from '@/components/ui/Table'
import { ApiError, errorMessage } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

export type FieldDef = {
  name: string
  label: string
  kind?: 'text' | 'number' | 'select' | 'time' | 'checkbox' | 'password' | 'email' | 'tel'
  required?: boolean
  options?: { value: string; label: string }[]
  hint?: string
  /** show the field only when adding, or only when editing */
  only?: 'create' | 'edit'
  step?: string
}

export type Values = Record<string, string>

type Props<T extends { id: number }> = {
  eyebrow?: string
  title: string
  description: string
  /** "supplier": used in "Add supplier" and "Supplier saved" */
  singular: string
  queryKey: string[]
  load: () => Promise<T[]>
  columns: { header: string; cell: (row: T) => ReactNode; num?: boolean }[]
  fields: FieldDef[]
  /** the form's starting values: the row when editing, or null when adding */
  initial: (row: T | null) => Values
  create: (values: Values) => Promise<unknown>
  update: (row: T, values: Values) => Promise<unknown>
  empty: { title: string; description: string }
  /** false when the signed-in role may look but not change */
  canEdit?: boolean
  /** keys other screens read too, refetched after a save */
  alsoInvalidate?: string[][]
  /** extra buttons or badges for a row, shown beside Edit */
  rowActions?: (row: T) => ReactNode
}

const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/** A list with Add and Edit for one kind of master data. The form is described by `fields`; the server's own refusals appear under the field they are about. */
export function MasterScreen<T extends { id: number }>(props: Props<T>) {
  const { eyebrow, title, description, singular, queryKey, load, columns, empty, canEdit = true } = props
  const list = useQuery({ queryKey, queryFn: load })
  const [editing, setEditing] = useState<T | 'new' | null>(null)

  return (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        description={description}
        actions={
          canEdit && (
            <Button onClick={() => setEditing('new')}>
              <Plus size={16} aria-hidden /> Add {singular}
            </Button>
          )
        }
      />
      <QueryBoundary query={list}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title={empty.title} description={empty.description} />
          ) : (
            <Reveal>
              <Table>
                <thead>
                  <tr>
                    {columns.map((c) => (
                      <th key={c.header} className={c.num ? 'num' : undefined}>
                        {c.header}
                      </th>
                    ))}
                    {canEdit && (
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      {columns.map((c) => (
                        <td key={c.header} className={c.num ? 'num' : undefined}>
                          {c.cell(row)}
                        </td>
                      ))}
                      {canEdit && (
                        <td>
                          <span className="row">
                            <Button variant="secondary" onClick={() => setEditing(row)} aria-label={`Edit ${singular} ${row.id}`}>
                              <Pencil size={14} aria-hidden /> Edit
                            </Button>
                            {props.rowActions?.(row)}
                          </span>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Reveal>
          )
        }
      </QueryBoundary>
      {editing && <MasterDialog {...props} row={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

function MasterDialog<T extends { id: number }>({
  singular,
  queryKey,
  fields,
  initial,
  create,
  update,
  alsoInvalidate = [],
  row,
  onClose,
}: Props<T> & { row: T | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const [values, setValues] = useState<Values>(() => initial(row))
  const [errors, setErrors] = useState<Values>({})
  const [formError, setFormError] = useState<string | null>(null)
  const shown = fields.filter((f) => !f.only || (f.only === 'create') === (row === null))
  const set = (name: string, value: string) => setValues((v) => ({ ...v, [name]: value }))

  const validate = () => {
    const next: Values = {}
    for (const f of shown) {
      const v = (values[f.name] ?? '').trim()
      if (f.required && !v && f.kind !== 'checkbox') next[f.name] = `Enter the ${f.label.toLowerCase()}`
      else if (f.kind === 'number' && v && !Number.isFinite(Number(v))) next[f.name] = 'Enter a number'
    }
    return next
  }

  const submit = () =>
    run(async () => {
      const found = validate()
      setErrors(found)
      setFormError(null)
      if (Object.keys(found).length) return
      try {
        if (row) await update(row, values)
        else await create(values)
        toast.success(`${sentence(singular)} ${row ? 'saved' : 'added'}`)
        for (const key of [queryKey, ...alsoInvalidate]) void queryClient.invalidateQueries({ queryKey: key })
        onClose()
      } catch (err) {
        const placed: Values = {}
        if (err instanceof ApiError) {
          const fieldMessages = err.fields ?? (err.field ? { [err.field]: err.body.message } : {})
          for (const [name, message] of Object.entries(fieldMessages)) if (shown.some((f) => f.name === name)) placed[name] = message
        }
        if (Object.keys(placed).length) setErrors(placed)
        else setFormError(errorMessage(err))
      }
    })

  return (
    <Dialog open onClose={onClose} title={row ? `Edit ${singular}` : `Add ${singular}`}>
      <form
        className="stack"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        {shown.map((f) =>
          f.kind === 'checkbox' ? (
            <label key={f.name} className="check-row">
              <input type="checkbox" checked={values[f.name] === 'true'} onChange={(e) => set(f.name, String(e.target.checked))} /> {f.label}
            </label>
          ) : (
            <Field key={f.name} label={f.label} hint={f.hint} error={errors[f.name]}>
              {(c) =>
                f.kind === 'select' ? (
                  <Select {...c} value={values[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)}>
                    <option value="">{f.required ? `Select a ${f.label.toLowerCase()}` : 'None'}</option>
                    {(f.options ?? []).map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <Input
                    {...c}
                    type={f.kind === 'number' ? 'text' : (f.kind ?? 'text')}
                    inputMode={f.kind === 'number' ? 'decimal' : undefined}
                    autoComplete={f.kind === 'password' ? 'new-password' : 'off'}
                    value={values[f.name] ?? ''}
                    onChange={(e) => set(f.name, e.target.value)}
                  />
                )
              }
            </Field>
          ),
        )}
        {formError && <Alert tone="error">{formError}</Alert>}
        <div className="row">
          <SubmitButton pending={pending}>{row ? 'Save changes' : `Add ${singular}`}</SubmitButton>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
