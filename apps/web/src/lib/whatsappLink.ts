/** The text that goes into WhatsApp: the message, and the tracking link on its own line when there is one. */
export function whatsappText(message: string, trackingUrl: string | null): string {
  const text = message.trim()
  return trackingUrl ? `${text}\n\nTrack my order: ${trackingUrl}` : text
}

/** A link that opens WhatsApp (phone, desktop or web) at this number with the message typed in. The sender only has to press send. */
export function whatsappLink(phoneDigits: string, message: string, trackingUrl: string | null): string {
  return `https://wa.me/${phoneDigits.replace(/\D/g, '')}?text=${encodeURIComponent(whatsappText(message, trackingUrl))}`
}
