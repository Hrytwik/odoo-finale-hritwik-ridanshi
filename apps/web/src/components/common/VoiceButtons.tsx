import { Mic, Square, Volume2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { useI18n } from '@/i18n/I18nContext'
import { canListen, canSpeak, hasVoiceFor, speak, stopSpeaking, useDictation, type ListenProblem } from '@/lib/speech'

/** Speak instead of type: the words are added to the box in the language chosen for the app. Hidden where the browser cannot listen. */
export function MicButton({ onText }: { onText: (text: string) => void }) {
  const { language, t } = useI18n()
  const { listening, start, stop } = useDictation(language.speech, onText, (problem: ListenProblem) =>
    toast.error(t(problem === 'blocked' ? 'voice.blocked' : problem === 'nothing' ? 'voice.heardNothing' : 'voice.unsupported')),
  )
  if (!canListen()) return null
  const label = listening ? t('voice.stop') : t('voice.speak')
  return (
    <Button type="button" variant="secondary" icon aria-label={label} title={label} aria-pressed={listening} onClick={listening ? stop : start}>
      {listening ? <Square size={16} aria-hidden /> : <Mic size={16} aria-hidden />}
    </Button>
  )
}

/** Reads a piece of text aloud in the chosen language. Hidden where the browser cannot speak. */
export function SpeakButton({ text }: { text: string }) {
  const { language, t } = useI18n()
  const [speaking, setSpeaking] = useState(false)
  useEffect(() => () => stopSpeaking(), [])
  if (!canSpeak()) return null
  const label = speaking ? t('voice.stopReading') : t('voice.readAloud')
  return (
    <button
      type="button"
      className="chat-chip"
      aria-label={label}
      title={label}
      onClick={() => {
        if (speaking) {
          stopSpeaking()
          setSpeaking(false)
          return
        }
        if (!hasVoiceFor(language.speech)) return void toast.error(t('voice.noVoice'))
        setSpeaking(true)
        speak(text, language.speech, () => setSpeaking(false))
      }}
    >
      {speaking ? <Square size={14} aria-hidden /> : <Volume2 size={14} aria-hidden />} {label}
    </button>
  )
}
