import { useCallback, useEffect, useRef, useState } from 'react'

/** The browser's own speech tools. Nothing is sent to our server: the browser listens and reads aloud by itself. */
type Alternative = { transcript: string }
type ResultList = ArrayLike<ArrayLike<Alternative> & { isFinal: boolean }>
type Recognition = {
  lang: string
  interimResults: boolean
  continuous: boolean
  onresult: ((e: { results: ResultList }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type RecognitionCtor = new () => Recognition

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export const canListen = () => recognitionCtor() !== null
export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined'

export type ListenProblem = 'unsupported' | 'blocked' | 'nothing'

/** Turns what was said into text, in the given language (a code like "hi-IN"). `onText` gets the final sentence. */
export function useDictation(lang: string, onText: (text: string) => void, onProblem: (problem: ListenProblem) => void) {
  const [listening, setListening] = useState(false)
  const active = useRef<Recognition | null>(null)
  const heard = useRef(false)

  useEffect(() => () => active.current?.abort(), [])

  const stop = useCallback(() => active.current?.stop(), [])

  const start = useCallback(() => {
    const Ctor = recognitionCtor()
    if (!Ctor) return onProblem('unsupported')
    active.current?.abort()
    const r = new Ctor()
    r.lang = lang
    r.interimResults = false
    r.continuous = false
    heard.current = false
    r.onresult = (e) => {
      const said = Array.from(e.results)
        .map((res) => res[0]?.transcript ?? '')
        .join(' ')
        .trim()
      if (said) {
        heard.current = true
        onText(said)
      }
    }
    r.onerror = (e) => {
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') onProblem('blocked')
      else if (e.error === 'no-speech') onProblem('nothing')
    }
    r.onend = () => {
      setListening(false)
      active.current = null
    }
    active.current = r
    setListening(true)
    try {
      r.start()
    } catch {
      setListening(false)
    }
  }, [lang, onText, onProblem])

  return { listening, start, stop }
}

/** Plain words for reading aloud: the bold marks and table bars the assistant writes are not spoken. */
export function speakable(text: string): string {
  return text
    .replace(/\*\*/g, '')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/\|/g, ', ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** True when this device has a voice for the language (matching "hi" of "hi-IN" is enough). */
export function hasVoiceFor(lang: string): boolean {
  if (!canSpeak()) return false
  const base = lang.split('-')[0].toLowerCase()
  const voices = window.speechSynthesis.getVoices()
  // some browsers load the voice list late; with an empty list we let the attempt go ahead
  return voices.length === 0 || voices.some((v) => v.lang.toLowerCase().startsWith(base))
}

export function speak(text: string, lang: string, onEnd: () => void) {
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(speakable(text))
  u.lang = lang
  u.onend = onEnd
  u.onerror = onEnd
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if (canSpeak()) window.speechSynthesis.cancel()
}
