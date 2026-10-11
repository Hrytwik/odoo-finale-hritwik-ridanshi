import { describe, expect, it } from 'vitest'
import { whatsappLink, whatsappText } from './whatsappLink'

describe('whatsappLink', () => {
  it('opens the number with the message typed in', () => {
    expect(whatsappLink('919845012345', 'Your order is late.', null)).toBe('https://wa.me/919845012345?text=Your%20order%20is%20late.')
  })
  it('puts the tracking link on its own line', () => {
    const url = whatsappLink('919845012345', 'Late.', 'https://mill.example/portal/orders/ORD-0001')
    expect(decodeURIComponent(url.split('?text=')[1])).toBe('Late.\n\nTrack my order: https://mill.example/portal/orders/ORD-0001')
  })
  it('keeps only the digits of the number', () => {
    expect(whatsappLink('+91 98450-12345', 'Hi', null).startsWith('https://wa.me/919845012345?')).toBe(true)
  })
  it('escapes characters that would break the link', () => {
    expect(whatsappLink('919845012345', 'A & B? 100%', null)).toContain('A%20%26%20B%3F%20100%25')
  })
  it('trims the message', () => expect(whatsappText('  Hi  ', null)).toBe('Hi'))
})
