import { describe, expect, it } from 'vitest'
import { generatePassword, LOGIN_ROLE_FOR_JOB, slipHtml, suggestUsername } from './credentials'
import { passwordProblem } from './passwordRules'

describe('suggestUsername', () => {
  it('uses the first name and the last initial', () => {
    expect(suggestUsername('Ravi Kumar', new Set())).toBe('ravi.k')
    expect(suggestUsername('Meena Devi', new Set())).toBe('meena.d')
    expect(suggestUsername('Anita Rao Nair', new Set())).toBe('anita.n')
  })
  it('uses just the name when there is only one', () => expect(suggestUsername('Imran', new Set())).toBe('imran'))
  it('drops dots, accents and capitals, and has a fallback', () => {
    expect(suggestUsername('  D. Joshi ', new Set())).toBe('d.j')
    expect(suggestUsername('', new Set())).toBe('user')
  })
  it('adds a number when the name is taken', () => {
    expect(suggestUsername('Ravi Kumar', new Set(['ravi.k']))).toBe('ravi.k2')
    expect(suggestUsername('Ravi Kumar', new Set(['ravi.k', 'ravi.k2']))).toBe('ravi.k3')
  })
})

describe('generatePassword', () => {
  it('is 12 characters in three groups, with letters, a capital and a number, and passes the password rules', () => {
    for (let i = 0; i < 200; i++) {
      const p = generatePassword()
      expect(p).toMatch(/^[A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4}$/)
      expect(p).toMatch(/[2-9]/)
      expect(p).toMatch(/[A-Z]/)
      expect(p).toMatch(/[a-z]/)
      expect(passwordProblem(p, 'ravi.k')).toBeNull()
    }
  })
  it('never uses the look-alike characters 0 O 1 l I', () => {
    for (let i = 0; i < 200; i++) expect(generatePassword()).not.toMatch(/[01OlI]/)
  })
  it('is different each time', () => expect(new Set(Array.from({ length: 50 }, () => generatePassword())).size).toBe(50))
})

describe('jobs and logins', () => {
  it('gives a login role to inspectors, storekeepers, supervisors and dispatch staff only', () => {
    expect(LOGIN_ROLE_FOR_JOB).toEqual({ inspector: 'qc', storekeeper: 'store', supervisor: 'supervisor', dispatch: 'dispatch' })
    expect(LOGIN_ROLE_FOR_JOB.operator).toBeUndefined()
  })
})

describe('slipHtml', () => {
  it('shows the username and password, and cannot be broken by odd characters in a name', () => {
    const html = slipHtml('<b>Ravi</b> & "Co"', 'ravi.k', 'Kf7x-Rm3p-Wq9z', 'https://mill.example')
    expect(html).toContain('Kf7x-Rm3p-Wq9z')
    expect(html).toContain('ravi.k')
    expect(html).not.toContain('<b>Ravi</b>')
    expect(html).toContain('&lt;b&gt;Ravi&lt;/b&gt; &amp; &quot;Co&quot;')
  })
})
