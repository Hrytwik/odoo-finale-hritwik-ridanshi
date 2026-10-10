import createClient from 'openapi-fetch'
import type { paths } from '@contracts/types'

/** Typed from the backend contract. Calls `/api/...` on this origin; Vite (dev) or Caddy proxies them to FastAPI. */
export const api = createClient<paths>({ baseUrl: '' })
