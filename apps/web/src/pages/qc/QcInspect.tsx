import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Plus, ScanSearch, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert } from '@/components/common/Alert'
import { PageHeader } from '@/components/common/PageHeader'
import { PhotoWithBoxes } from '@/components/common/PhotoWithBoxes'
import { QueryBoundary } from '@/components/common/QueryBoundary'
import { SubmitButton } from '@/components/common/SubmitButton'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field, Input, Select, Textarea } from '@/components/ui/Field'
import { useMe } from '@/lib/auth'
import { useI18n } from '@/i18n/I18nContext'
import { DEFECT_LABEL } from '@/lib/defects'
import { useDefectLabel } from '@/lib/useDefectLabel'
import { api, call, errorMessage, type components } from '@/lib/api'
import type { Key } from '@/i18n/en'
import { useSubmitLock } from '@/lib/forms'
import { formatMetres } from '@/lib/format'

type Verdict = components['schemas']['InspectionIn']['verdict']
type DefectType = components['schemas']['DefectIn']['defect_type']
type Suggestion = components['schemas']['AiSuggestion']
type Analysis = components['schemas']['AnalyzeOut']

type DefectRow = { type: DefectType; count: string; fromAi: boolean }

const VERDICTS: { value: Verdict; label: Key; hint: Key }[] = [
  { value: 'pass', label: 'qc.verdict.pass', hint: 'qc.verdict.passHint' },
  { value: 'rework', label: 'qc.verdict.rework', hint: 'qc.verdict.reworkHint' },
  { value: 'reject', label: 'qc.verdict.reject', hint: 'qc.verdict.rejectHint' },
]
const VERDICT_WORD: Record<Verdict, Key> = { pass: 'qc.verdictWord.pass', rework: 'qc.verdictWord.rework', reject: 'qc.verdictWord.reject' }

/** Counts the model's boxes per defect type: three boxes, two of them holes, becomes 2 holes and 1 stain. */
function rowsFromSuggestion(s: Suggestion): DefectRow[] {
  const counts = new Map<DefectType, number>()
  for (const b of s.boxes) counts.set(b.defect_type, (counts.get(b.defect_type) ?? 0) + 1)
  return [...counts].map(([type, count]) => ({ type, count: String(count), fromAi: true }))
}

export default function QcInspect() {
  const { rollCode = '' } = useParams()
  const passport = useQuery({
    queryKey: ['rolls', rollCode],
    queryFn: () => call(api.GET('/api/rolls/{roll_code}/passport', { params: { path: { roll_code: rollCode } } })),
    enabled: !!rollCode,
  })
  return <QueryBoundary query={passport}>{(p) => <Inspection roll={p.roll} />}</QueryBoundary>
}

function Inspection({ roll }: { roll: components['schemas']['RollOut'] }) {
  const { t } = useI18n()
  const defectLabel = useDefectLabel()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { run, pending } = useSubmitLock()
  // the server records the inspector from the login's linked worker; a login without one (the owner's) cannot record a verdict
  const me = useMe()
  const noInspector = me.data !== undefined && me.data.worker_id === null

  const [photo, setPhoto] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [photoPath, setPhotoPath] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [analysing, setAnalysing] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  const [verdict, setVerdict] = useState<Verdict | ''>('')
  const [defects, setDefects] = useState<DefectRow[]>([])
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState<{ verdict?: string; defects?: string }>({})
  const [formError, setFormError] = useState<string | null>(null)

  // free the photo preview when it changes or the screen closes
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview)
    }
  }, [preview])

  const suggestion = analysis?.suggestion ?? null
  const overriding = !!suggestion && !!verdict && verdict !== suggestion.verdict
  const waiting = roll.status === 'awaiting_qc'

  function choosePhoto(file: File | null) {
    setPhoto(file)
    setPhotoPath(null) // a new photo must be uploaded again
    setAnalysis(null)
    setAnalysisError(null)
    setPreview(file ? URL.createObjectURL(file) : null)
  }

  /** Uploads the photo once, then asks the model. A failure here never blocks the inspector: checking works without it. */
  async function analyse() {
    if (!photo) return
    setAnalysing(true)
    setAnalysisError(null)
    try {
      let path = photoPath
      if (!path) {
        const data = new FormData()
        data.append('file', photo)
        path = (await call(api.POST('/api/uploads', { body: { file: photo as unknown as string }, bodySerializer: () => data }))).path
        setPhotoPath(path)
      }
      const result = await call(api.POST('/api/qc/analyze', { body: { photo_path: path } }))
      setAnalysis(result)
      if (result.suggestion) {
        setVerdict(result.suggestion.verdict)
        setDefects(rowsFromSuggestion(result.suggestion))
      }
    } catch {
      setAnalysisError(t('qc.inspect.analyseFailed'))
    } finally {
      setAnalysing(false)
    }
  }

  function validDefects() {
    return defects
      .map((d) => ({ ...d, n: Number(d.count) }))
      .filter((d) => Number.isInteger(d.n) && d.n >= 1 && d.n <= 1000)
  }

  const submit = () =>
    run(async () => {
      const next: typeof errors = {}
      const good = validDefects()
      if (!verdict) next.verdict = t('qc.inspect.chooseVerdict')
      else if (verdict !== 'pass' && good.length === 0) next.defects = t('qc.inspect.needDefect')
      setErrors(next)
      setFormError(null)
      if (next.verdict || next.defects || !verdict) return
      const aiTypes = new Set(suggestion?.boxes.map((b) => b.defect_type))
      try {
        await call(
          api.POST('/api/qc/inspections', {
            body: {
              roll_code: roll.code,
              verdict,
              defects: good.map((d) => ({ defect_type: d.type, count: d.n, ai_detected: aiTypes.has(d.type) })),
              ...(photoPath ? { photo_path: photoPath } : {}),
              ...(suggestion ? { ai_suggestion: suggestion } : {}),
              ...(notes.trim() ? { notes: notes.trim() } : {}),
            },
          }),
        )
        toast.success(t('qc.inspect.recorded', { code: roll.code, verdict: t(VERDICT_WORD[verdict]) }))
        for (const queryKey of [['qc'], ['rolls'], ['orders'], ['insights']]) void queryClient.invalidateQueries({ queryKey })
        navigate('/qc')
      } catch (err) {
        setFormError(errorMessage(err))
      }
    })

  return (
    <>
      <PageHeader title={t('qc.inspect.title', { code: roll.code })} description={`${roll.order_code} · ${roll.fabric}, ${roll.colour} · ${formatMetres(roll.metres)}`} />
      <div className="stack" style={{ maxWidth: 760 }}>
        {!waiting && <Alert tone="info">{t('qc.inspect.notWaiting', { status: t(`status.roll.${roll.status}` as Key) })}</Alert>}

        <Card title={t('qc.inspect.step1')}>
          <div className="stack">
            <Field label={t('qc.inspect.photo')} hint={photo ? photo.name : t('qc.inspect.photoHint')}>
              {(c) => (
                <label className="file-pick">
                  <Camera size={18} aria-hidden />
                  <span>{photo ? t('store.receive.photoChange') : t('store.receive.photoTake')}</span>
                  <input {...c} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => choosePhoto(e.target.files?.[0] ?? null)} />
                </label>
              )}
            </Field>
            {preview && (
              <>
                <PhotoWithBoxes src={preview} boxes={suggestion?.boxes ?? []} alt={t('qc.inspect.photoAlt')} />
                <div>
                  <Button variant="secondary" onClick={analyse} disabled={analysing}>
                    <ScanSearch size={16} aria-hidden /> {analysing ? t('qc.inspect.analysing') : analysis ? t('qc.inspect.analyseAgain') : t('qc.inspect.analyse')}
                  </Button>
                </div>
              </>
            )}
            {analysisError && <Alert tone="error">{analysisError}</Alert>}
            {analysis && <AnalysisNote analysis={analysis} />}
          </div>
        </Card>

        <form
          noValidate
          className="stack"
          onSubmit={(e) => {
            e.preventDefault()
            void submit()
          }}
        >
          <Card title={t('qc.inspect.step2')}>
            <div className="stack">
              <div role="radiogroup" aria-label={t('qc.inspect.verdictGroup')} className="verdicts">
                {VERDICTS.map((v) => (
                  <label key={v.value} className={`verdict verdict-${v.value}${verdict === v.value ? ' is-picked' : ''}`}>
                    <input type="radio" name="verdict" value={v.value} checked={verdict === v.value} onChange={() => setVerdict(v.value)} className="sr-only" aria-label={t(v.label)} />
                    <strong>{t(v.label)}</strong>
                    <span className="text-sm">{t(v.hint)}</span>
                  </label>
                ))}
              </div>
              {errors.verdict && <p className="field-error">{errors.verdict}</p>}
              {overriding && suggestion && (
                <Alert tone="info">
                  {t('qc.inspect.overriding', { verdict: t(VERDICT_WORD[suggestion.verdict]) })}
                </Alert>
              )}
            </div>
          </Card>

          <Card title={t('qc.inspect.step3')}>
            <div className="stack">
              {defects.map((d, i) => (
                <div key={i} className="defect-row">
                  <Field label={t('qc.inspect.defectType')}>
                    {(c) => (
                      <Select {...c} value={d.type} onChange={(e) => setDefects((rows) => rows.map((r, j) => (j === i ? { ...r, type: e.target.value as DefectType } : r)))}>
                        {(Object.keys(DEFECT_LABEL) as DefectType[]).map((dt) => (
                          <option key={dt} value={dt}>
                            {defectLabel(dt)}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label={t('qc.inspect.howMany')}>
                    {(c) => <Input {...c} type="number" inputMode="numeric" min={1} value={d.count} onChange={(e) => setDefects((rows) => rows.map((r, j) => (j === i ? { ...r, count: e.target.value } : r)))} />}
                  </Field>
                  <Button variant="ghost" icon aria-label={t('qc.inspect.removeDefect')} onClick={() => setDefects((rows) => rows.filter((_, j) => j !== i))}>
                    <Trash2 size={16} aria-hidden />
                  </Button>
                </div>
              ))}
              <div>
                <Button variant="secondary" onClick={() => setDefects((rows) => [...rows, { type: 'hole', count: '1', fromAi: false }])}>
                  <Plus size={16} aria-hidden /> {t('qc.inspect.addDefect')}
                </Button>
              </div>
              {errors.defects && <p className="field-error">{errors.defects}</p>}
              <Field label={t('qc.inspect.notes')}>{(c) => <Textarea {...c} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            </div>
          </Card>

          {noInspector && (
            <Alert tone="info">
              {t('qc.inspect.noInspector')}
            </Alert>
          )}
          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} disabled={noInspector} block>
            {t('qc.inspect.record')}
          </SubmitButton>
        </form>
      </div>
    </>
  )
}

function AnalysisNote({ analysis }: { analysis: Analysis }) {
  const { t } = useI18n()
  if (!analysis.suggestion) {
    return <Alert tone="info">{analysis.message ?? t('qc.inspect.noSuggestion')}</Alert>
  }
  return (
    <div className="stack-sm">
      <p>
        <strong>{t('qc.inspect.aiSuggests', { verdict: t(VERDICT_WORD[analysis.suggestion.verdict]), found: t(analysis.suggestion.boxes.length === 1 ? 'defect.count.one' : 'defect.count.many', { count: analysis.suggestion.boxes.length }) })}</strong>{' '}
        <span className="muted text-sm">({analysis.suggestion.model_version})</span>
      </p>
      {!analysis.available && <Badge tone="amber">{t('qc.inspect.unvalidated')}</Badge>}
      {analysis.message && <p className="muted text-sm">{analysis.message}</p>}
      <p className="muted text-sm">{t('qc.inspect.onlySuggestion')}</p>
    </div>
  )
}
