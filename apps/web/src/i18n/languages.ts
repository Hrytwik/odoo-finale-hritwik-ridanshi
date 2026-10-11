export type LangCode = 'en' | 'hi' | 'kn' | 'ta' | 'te' | 'mr' | 'bn' | 'gu' | 'ml' | 'pa'

export type Language = {
  code: LangCode
  /** the name in English, for the Copilot to be told which language to answer in */
  english: string
  /** the name in its own script, which is what a person looks for in the list */
  native: string
  /** the browser's speech tools use these region codes, for listening and for reading aloud */
  speech: string
}

/** Languages the app can show. English is the base: anything not yet translated falls back to it, never to a blank. */
export const LANGUAGES: Language[] = [
  { code: 'en', english: 'English', native: 'English', speech: 'en-IN' },
  { code: 'hi', english: 'Hindi', native: 'हिन्दी', speech: 'hi-IN' },
  { code: 'kn', english: 'Kannada', native: 'ಕನ್ನಡ', speech: 'kn-IN' },
  { code: 'ta', english: 'Tamil', native: 'தமிழ்', speech: 'ta-IN' },
  { code: 'te', english: 'Telugu', native: 'తెలుగు', speech: 'te-IN' },
  { code: 'mr', english: 'Marathi', native: 'मराठी', speech: 'mr-IN' },
  { code: 'bn', english: 'Bengali', native: 'বাংলা', speech: 'bn-IN' },
  { code: 'gu', english: 'Gujarati', native: 'ગુજરાતી', speech: 'gu-IN' },
  { code: 'ml', english: 'Malayalam', native: 'മലയാളം', speech: 'ml-IN' },
  { code: 'pa', english: 'Punjabi', native: 'ਪੰਜਾਬੀ', speech: 'pa-IN' },
]

export const DEFAULT_LANGUAGE: LangCode = 'en'

export const isLangCode = (value: unknown): value is LangCode => LANGUAGES.some((l) => l.code === value)

export const languageOf = (code: LangCode): Language => LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0]
