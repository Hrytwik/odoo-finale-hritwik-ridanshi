import { describe, expect, it } from 'vitest'
import { passwordProblem } from './passwordRules'

describe('passwordProblem', () => {
  it('accepts a password with letters and a number of enough length', () => {
    expect(passwordProblem('good-pass-9', 'ravi')).toBeNull()
    expect(passwordProblem('Abcdefg1', 'ravi')).toBeNull()
  })

  it('wants at least 8 characters', () => {
    expect(passwordProblem('a1', 'ravi')).toMatch(/at least 8/)
    expect(passwordProblem('abcdef1', 'ravi')).toMatch(/at least 8/)
  })

  it('wants both letters and a number', () => {
    expect(passwordProblem('onlyletters', 'ravi')).toMatch(/letters and at least one number/)
    expect(passwordProblem('12345678901', 'ravi')).toMatch(/letters and at least one number/)
  })

  it('refuses the most common passwords, in any case', () => {
    expect(passwordProblem('password123', 'ravi')).toMatch(/too common/)
    expect(passwordProblem('PassWord123', 'ravi')).toMatch(/too common/)
  })

  it('refuses a password that contains the username', () => {
    expect(passwordProblem('xxravi-pass9', 'ravi')).toMatch(/username/)
    expect(passwordProblem('xxRAVI-pass9', 'ravi')).toMatch(/username/)
  })

  it('does not match a very short username', () => {
    expect(passwordProblem('ra-pass-12345', 'ra')).toBeNull()
  })

  it('counts bytes, not letters, against the 72 byte limit', () => {
    expect(passwordProblem('a1' + 'é'.repeat(40), 'ravi')).toMatch(/at most 72 bytes/)
    expect(passwordProblem('a1' + 'b'.repeat(70), 'ravi')).toBeNull()
  })
})
