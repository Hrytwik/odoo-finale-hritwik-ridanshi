import { languageOf } from '../area'
import { store } from '../areas/store'
import type { Key } from '../en'
import type { LangCode } from '../languages'
import { bn } from './bn'
import { gu } from './gu'
import { hi } from './hi'
import { kn } from './kn'
import { ml } from './ml'
import { mr } from './mr'
import { pa } from './pa'
import { ta } from './ta'
import { te } from './te'

/** Every language except English, which lives in `en.ts` and is the fallback for anything missing here. */
type Words = Partial<Record<Key, string>>
const areas = (code: Exclude<LangCode, 'en'>) => languageOf(code, store) as Words

export const locales: Partial<Record<LangCode, Words>> = {
  hi: { ...hi, ...areas('hi') },
  kn: { ...kn, ...areas('kn') },
  ta: { ...ta, ...areas('ta') },
  te: { ...te, ...areas('te') },
  mr: { ...mr, ...areas('mr') },
  bn: { ...bn, ...areas('bn') },
  gu: { ...gu, ...areas('gu') },
  ml: { ...ml, ...areas('ml') },
  pa: { ...pa, ...areas('pa') },
}
