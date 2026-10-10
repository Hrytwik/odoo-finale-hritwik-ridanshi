import { describe, expect, it } from 'vitest'
import { parseRollCode, rollUrl } from './rollCode'

describe('parseRollCode', () => {
  it('reads a plain roll code', () => {
    expect(parseRollCode('R-0142')).toBe('R-0142')
  })

  it('reads the address on a printed QR tag', () => {
    expect(parseRollCode('https://192.168.1.23:8443/r/R-0142')).toBe('R-0142')
    expect(parseRollCode('http://localhost:3000/r/R-0007?x=1')).toBe('R-0007')
  })

  it('ignores case and surrounding spaces, and returns the code in capitals', () => {
    expect(parseRollCode('  r-0142 \n')).toBe('R-0142')
  })

  it('accepts codes with more than four digits', () => {
    expect(parseRollCode('R-12345')).toBe('R-12345')
  })

  it('rejects things that are not a roll code', () => {
    expect(parseRollCode('')).toBeNull()
    expect(parseRollCode('hello')).toBeNull()
    expect(parseRollCode('L-0017')).toBeNull()
    expect(parseRollCode('R-')).toBeNull()
    expect(parseRollCode('https://evil.example/login')).toBeNull()
  })

  it('does not pick a roll code out of the middle of other text', () => {
    expect(parseRollCode('see R-0142 for details')).toBeNull()
    expect(parseRollCode('XR-0142')).toBeNull()
  })
})

describe('rollUrl', () => {
  it('builds the address that goes into the QR tag', () => {
    expect(rollUrl('R-0142', 'https://192.168.1.23:8443')).toBe('https://192.168.1.23:8443/r/R-0142')
  })
})
