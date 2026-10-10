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
import { DEFECT_LABEL } from '@/lib/defects'
import { api, call, errorMessage, type components } from '@/lib/api'
import { useSubmitLock } from '@/lib/forms'
import { formatMetres } from '@/lib/format'

type Verdict = components['schemas']['InspectionIn']['verdict']
type DefectType = components['schemas']['DefectIn']['defect_type']
type Suggestion = components['schemas']['AiSuggestion']
type Analysis = components['schemas']['AnalyzeOut']

type DefectRow = { type: DefectType; count: string; fromAi: boolean }

const VERDICTS: { value: Verdict; label: string; hint: string }[] = [
  { value: 'pass', label: 'Pass', hint: 'Good to store and sell' },
  { value: 'rework', label: 'Rework', hint: 'Can be mended or re-dyed' },
  { value: 'reject', label: 'Reject', hint: 'Cannot be saved' },
]
const VERDICT_WORD: Record<Verdict, string> = { pass: 'pass', rework: 'rework', reject: 'reject' }

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
      setAnalysisError('Could not analyse the photo. You can still check the roll by eye and record the verdict.')
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
      if (!verdict) next.verdict = 'Choose a verdict'
      else if (verdict !== 'pass' && good.length === 0) next.defects = 'Add at least one defect for a rework or reject'
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
        toast.success(`${roll.code}: ${VERDICT_WORD[verdict]} recorded`)
        for (const queryKey of [['qc'], ['rolls'], ['orders'], ['insights']]) void queryClient.invalidateQueries({ queryKey })
        navigate('/qc')
      } catch (err) {
        setFormError(errorMessage(err))
      }
    })

  return (
    <>
      <PageHeader title={`Inspect ${roll.code}`} description={`${roll.order_code} · ${roll.fabric}, ${roll.colour} · ${formatMetres(roll.metres)}`} />
      <div className="stack" style={{ maxWidth: 760 }}>
        {!waiting && <Alert tone="info">This roll is not waiting for a quality check (it is {roll.status.replace('_', ' ')}). You can look, but the server will refuse a new verdict.</Alert>}

        <Card title="1. Photograph the cloth (optional)">
          <div className="stack">
            <Field label="Photo" hint={photo ? photo.name : 'Take a photo of the stretch you are checking'}>
              {(c) => (
                <label className="file-pick">
                  <Camera size={18} aria-hidden />
                  <span>{photo ? 'Change photo' : 'Take or choose a photo'}</span>
                  <input {...c} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(e) => choosePhoto(e.target.files?.[0] ?? null)} />
                </label>
              )}
            </Field>
            {preview && (
              <>
                <PhotoWithBoxes src={preview} boxes={suggestion?.boxes ?? []} alt="Cloth under inspection" />
                <div>
                  <Button variant="secondary" onClick={analyse} disabled={analysing}>
                    <ScanSearch size={16} aria-hidden /> {analysing ? 'Analysing…' : analysis ? 'Analyse photo again' : 'Analyse photo'}
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
          <Card title="2. Your verdict">
            <div className="stack">
              <div role="radiogroup" aria-label="Verdict" className="verdicts">
                {VERDICTS.map((v) => (
                  <label key={v.value} className={`verdict verdict-${v.value}${verdict === v.value ? ' is-picked' : ''}`}>
                    <input type="radio" name="verdict" value={v.value} checked={verdict === v.value} onChange={() => setVerdict(v.value)} className="sr-only" aria-label={v.label} />
                    <strong>{v.label}</strong>
                    <span className="text-sm">{v.hint}</span>
                  </label>
                ))}
              </div>
              {errors.verdict && <p className="field-error">{errors.verdict}</p>}
              {overriding && suggestion && (
                <Alert tone="info">
                  You are overriding the AI, which suggested <strong>{VERDICT_WORD[suggestion.verdict]}</strong>. Your verdict stands, and the override is recorded.
                </Alert>
              )}
            </div>
          </Card>

          <Card title="3. Defects found">
            <div className="stack">
              {defects.map((d, i) => (
                <div key={i} className="defect-row">
                  <Field label="Defect type">
                    {(c) => (
                      <Select {...c} value={d.type} onChange={(e) => setDefects((rows) => rows.map((r, j) => (j === i ? { ...r, type: e.target.value as DefectType } : r)))}>
                        {(Object.keys(DEFECT_LABEL) as DefectType[]).map((t) => (
                          <option key={t} value={t}>
                            {DEFECT_LABEL[t]}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label="How many">
                    {(c) => <Input {...c} type="number" inputMode="numeric" min={1} value={d.count} onChange={(e) => setDefects((rows) => rows.map((r, j) => (j === i ? { ...r, count: e.target.value } : r)))} />}
                  </Field>
                  <Button variant="ghost" icon aria-label="Remove defect" onClick={() => setDefects((rows) => rows.filter((_, j) => j !== i))}>
                    <Trash2 size={16} aria-hidden />
                  </Button>
                </div>
              ))}
              <div>
                <Button variant="secondary" onClick={() => setDefects((rows) => [...rows, { type: 'hole', count: '1', fromAi: false }])}>
                  <Plus size={16} aria-hidden /> Add defect
                </Button>
              </div>
              {errors.defects && <p className="field-error">{errors.defects}</p>}
              <Field label="Notes (optional)">{(c) => <Textarea {...c} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            </div>
          </Card>

          {noInspector && (
            <Alert tone="info">
              Your login is not linked to an inspector, so you cannot record a verdict. The owner can link a worker to this login on the Users screen.
            </Alert>
          )}
          {formError && <Alert tone="error">{formError}</Alert>}
          <SubmitButton pending={pending} disabled={noInspector} block>
            Record verdict
          </SubmitButton>
        </form>
      </div>
    </>
  )
}

function AnalysisNote({ analysis }: { analysis: Analysis }) {
  if (!analysis.suggestion) {
    return <Alert tone="info">{analysis.message ?? 'The model gave no suggestion. Check the roll by eye.'}</Alert>
  }
  return (
    <div className="stack-sm">
      <p>
        <strong>AI suggests:</strong> {VERDICT_WORD[analysis.suggestion.verdict]}, {analysis.suggestion.boxes.length} {analysis.suggestion.boxes.length === 1 ? 'defect' : 'defects'} found{' '}
        <span className="muted text-sm">({analysis.suggestion.model_version})</span>
      </p>
      {!analysis.available && <Badge tone="amber">Unvalidated suggestion</Badge>}
      {analysis.message && <p className="muted text-sm">{analysis.message}</p>}
      <p className="muted text-sm">It is only a suggestion. You decide, and every change you make is recorded.</p>
    </div>
  )
}
