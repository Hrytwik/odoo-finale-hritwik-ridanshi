import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
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
import { useI18n } from '@/i18n/I18nContext'
import { ApiError, api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'

type Fabric = components['schemas']['FabricTypeOut']
type Line = { yarn: string; kg: string }
type Form = { name: string; width: string; wastage: string; recipe: Line[] }

/** Fabric types and the yarn recipe for each: how many kg of which yarn go into a metre. */
export default function FabricTypes() {
  const { t } = useI18n()
  const fabrics = useQuery({ queryKey: ['master', 'fabric-types'], queryFn: () => call(api.GET('/api/fabric-types')) })
  const [editing, setEditing] = useState<Fabric | 'new' | null>(null)
  return (
    <>
      <PageHeader
        eyebrow={t('nav.group.Master data')}
        title={t('nav.fabricTypes')}
        description={t('fabric.description')}
        actions={
          <Button onClick={() => setEditing('new')}>
            <Plus size={16} aria-hidden /> {t('admin.add', { noun: t('fabric.noun') })}
          </Button>
        }
      />
      <QueryBoundary query={fabrics}>
        {(rows) =>
          rows.length === 0 ? (
            <EmptyState title={t('fabric.emptyTitle')} description={t('fabric.emptyDescription')} />
          ) : (
            <Reveal>
              <Table>
                <thead>
                  <tr>
                    <th>{t('common.name')}</th>
                    <th className="num">{t('fabric.col.width')}</th>
                    <th className="num">{t('fabric.col.wastage')}</th>
                    <th>{t('fabric.col.yarnPerMetre')}</th>
                    <th>
                      <span className="sr-only">{t('money.actions')}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((f) => (
                    <tr key={f.id}>
                      <td>
                        <strong>{f.name}</strong>
                      </td>
                      <td className="num">{t('fabric.inches', { n: f.width_in })}</td>
                      <td className="num">{f.wastage_pct}%</td>
                      <td>{f.recipe.map((l) => t('fabric.recipeLine', { code: l.yarn_type_code, kg: l.kg_per_metre })).join(' + ')}</td>
                      <td>
                        <Button variant="secondary" onClick={() => setEditing(f)} aria-label={t('admin.editAria', { noun: t('fabric.noun'), id: f.name })}>
                          <Pencil size={14} aria-hidden /> {t('admin.editButton')}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Reveal>
          )
        }
      </QueryBoundary>
      {editing && <FabricDialog fabric={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

function FabricDialog({ fabric, onClose }: { fabric: Fabric | null; onClose: () => void }) {
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  const yarns = useQuery({ queryKey: ['master', 'yarn-types'], queryFn: () => call(api.GET('/api/yarn-types')) })
  const [form, setForm] = useState<Form>(() => ({
    name: fabric?.name ?? '',
    width: fabric ? String(fabric.width_in) : '',
    wastage: fabric ? String(fabric.wastage_pct) : '5',
    recipe: fabric ? fabric.recipe.map((l) => ({ yarn: String(l.yarn_type_id), kg: String(l.kg_per_metre) })) : [{ yarn: '', kg: '' }],
  }))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const setLine = (i: number, patch: Partial<Line>) => setForm((f) => ({ ...f, recipe: f.recipe.map((l, j) => (j === i ? { ...l, ...patch } : l)) }))

  const validate = () => {
    const next: Record<string, string> = {}
    if (!form.name.trim()) next.name = t('fabric.err.name')
    if (!(Number(form.width) > 0)) next.width = t('fabric.err.width')
    if (!(Number(form.wastage) >= 0) || form.wastage.trim() === '') next.wastage = t('fabric.err.wastage')
    const chosen = form.recipe.map((l) => l.yarn)
    if (form.recipe.some((l) => !l.yarn || !(Number(l.kg) > 0))) next.recipe = t('fabric.err.recipeLine')
    else if (new Set(chosen).size !== chosen.length) next.recipe = t('fabric.err.recipeOnce')
    return next
  }

  const submit = () =>
    run(async () => {
      const found = validate()
      setErrors(found)
      setFormError(null)
      if (Object.keys(found).length) return
      const body = {
        name: form.name.trim(),
        width_in: Number(form.width),
        wastage_pct: Number(form.wastage),
        recipe: form.recipe.map((l) => ({ yarn_type_id: Number(l.yarn), kg_per_metre: Number(l.kg) })),
      }
      try {
        if (fabric) await call(api.PATCH('/api/fabric-types/{item_id}', { params: { path: { item_id: fabric.id } }, body }))
        else await call(api.POST('/api/fabric-types', { body }))
        toast.success(t(fabric ? 'admin.saved' : 'admin.added', { noun: t('fabric.noun').charAt(0).toUpperCase() + t('fabric.noun').slice(1) }))
        void queryClient.invalidateQueries({ queryKey: ['master', 'fabric-types'] })
        onClose()
      } catch (err) {
        const placed: Record<string, string> = {}
        if (err instanceof ApiError) {
          const known: Record<string, string> = { name: 'name', width_in: 'width', wastage_pct: 'wastage', recipe: 'recipe' }
          for (const [name, message] of Object.entries(err.fields ?? (err.field ? { [err.field]: err.body.message } : {}))) if (known[name]) placed[known[name]] = message
        }
        if (Object.keys(placed).length) setErrors(placed)
        else setFormError(errorMessage(err))
      }
    })

  return (
    <Dialog open onClose={onClose} title={fabric ? t('admin.edit', { noun: t('fabric.noun') }) : t('admin.add', { noun: t('fabric.noun') })}>
      <form
        className="stack"
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          void submit()
        }}
      >
        <Field label={t('common.name')} error={errors.name}>
          {(c) => <Input {...c} autoComplete="off" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />}
        </Field>
        <div className="grid-fields">
          <Field label={t('fabric.widthInches')} error={errors.width}>
            {(c) => <Input {...c} inputMode="decimal" autoComplete="off" value={form.width} onChange={(e) => setForm({ ...form, width: e.target.value })} />}
          </Field>
          <Field label={t('fabric.wastagePct')} error={errors.wastage}>
            {(c) => <Input {...c} inputMode="decimal" autoComplete="off" value={form.wastage} onChange={(e) => setForm({ ...form, wastage: e.target.value })} />}
          </Field>
        </div>
        <fieldset className="recipe">
          <legend>{t('fabric.col.yarnPerMetre')}</legend>
          {form.recipe.map((l, i) => (
            <div key={i} className="recipe-line">
              <Select aria-label={t('fabric.yarnN', { n: i + 1 })} value={l.yarn} onChange={(e) => setLine(i, { yarn: e.target.value })}>
                <option value="">{t('fabric.selectYarn')}</option>
                {(yarns.data ?? []).map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.code} · {y.name}
                  </option>
                ))}
              </Select>
              <Input aria-label={t('fabric.kgForYarn', { n: i + 1 })} inputMode="decimal" placeholder={t('fabric.kgPerM')} autoComplete="off" value={l.kg} onChange={(e) => setLine(i, { kg: e.target.value })} />
              {form.recipe.length > 1 && (
                <Button variant="ghost" icon aria-label={t('fabric.removeYarn', { n: i + 1 })} onClick={() => setForm({ ...form, recipe: form.recipe.filter((_, j) => j !== i) })}>
                  <Trash2 size={16} aria-hidden />
                </Button>
              )}
            </div>
          ))}
          {errors.recipe && <p className="field-error">{errors.recipe}</p>}
          <Button variant="secondary" onClick={() => setForm({ ...form, recipe: [...form.recipe, { yarn: '', kg: '' }] })}>
            <Plus size={14} aria-hidden /> {t('fabric.addYarn')}
          </Button>
        </fieldset>
        {formError && <Alert tone="error">{formError}</Alert>}
        <div className="row">
          <SubmitButton pending={pending}>{fabric ? t('admin.saveChanges') : t('admin.add', { noun: t('fabric.noun') })}</SubmitButton>
          <Button variant="secondary" onClick={onClose}>
            {t('dispatch.cancel')}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
