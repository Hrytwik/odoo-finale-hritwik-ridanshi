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
export const locales: Partial<Record<LangCode, Partial<Record<Key, string>>>> = { hi, kn, ta, te, mr, bn, gu, ml, pa }
