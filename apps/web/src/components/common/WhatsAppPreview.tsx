import { ExternalLink } from 'lucide-react'

/** How a message will look on the buyer's phone: a chat bubble with the link to follow the order, as the shop apps send. */
export function WhatsAppPreview({ message, withTracking, time = 'now' }: { message: string; withTracking: boolean; time?: string }) {
  return (
    <figure className="wa-preview" aria-label="Preview of the WhatsApp message">
      <figcaption className="wa-from">
        <span className="wa-avatar" aria-hidden>
          EM
        </span>
        <span>
          Everest Mills <small>Business account</small>
        </span>
      </figcaption>
      <div className="wa-bubble">
        <p>{message || '…'}</p>
        <span className="wa-time">{time}</span>
        {withTracking && (
          <span className="wa-button">
            <ExternalLink size={14} aria-hidden /> Track my order
          </span>
        )}
      </div>
    </figure>
  )
}
