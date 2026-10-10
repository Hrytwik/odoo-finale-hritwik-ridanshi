/**
 * How the message will look in WhatsApp, as it is really sent: the sentence, then the tracking link on its own line.
 * (A tap-able button needs a business sender with an approved template, so none is drawn here.)
 */
export function WhatsAppPreview({ message, trackingUrl, time = 'now' }: { message: string; trackingUrl: string | null; time?: string }) {
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
        <p>{message || '\u2026'}</p>
        {trackingUrl && (
          <p>
            Track my order: <span className="wa-link">{trackingUrl}</span>
          </p>
        )}
        <span className="wa-time">{time}</span>
      </div>
    </figure>
  )
}
