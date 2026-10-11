"""Sending a WhatsApp message through a Twilio account (the WhatsApp sandbox, or a business sender).

Plain HTTPS from the standard library, like the language-model adapters, so there is nothing to install and tests can
swap the transport. The account token is read only here and is never put into an error message or a reply.
"""
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import MessagingSettings
from app.modules.llm import crypto

TWILIO_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
DEFAULT_COUNTRY = "91"  # a ten-digit number is taken to be an Indian mobile number

PostForm = Callable[[str, dict[str, str], dict[str, str], float], dict]


@dataclass
class WhatsAppConfig:
    account_sid: str | None
    auth_token: str | None
    from_number: str | None
    public_url: str | None
    enabled: bool
    content_sid: str | None = None

    @property
    def ready(self) -> bool:
        """Switched on, and everything needed to send is filled in."""
        return bool(self.enabled and self.account_sid and self.auth_token and self.from_number)


@dataclass
class SendResult:
    status: str  # sent | failed | skipped
    detail: str | None = None
    sid: str | None = None


def load_config(db: Session) -> WhatsAppConfig:
    row = db.get(MessagingSettings, 1)
    if row is None:
        return WhatsAppConfig(None, None, None, None, False)
    token = crypto.decrypt_key(row.auth_token_encrypted) if row.auth_token_encrypted else None
    return WhatsAppConfig(row.account_sid, token, row.from_number, row.public_url, row.enabled, row.content_sid)


def normalise_phone(raw: str | None) -> str | None:
    """A phone number as +<country><number>, or None if it cannot be one. Spaces, dashes and brackets are ignored."""
    if not raw:
        return None
    text = raw.strip()
    digits = re.sub(r"\D", "", text)
    if re.match(r"^[^\d+]*\+", text):  # a plus sign, possibly after a bracket or a space
        number = digits
    elif re.match(r"^[^\d]*00", text):
        number = digits[2:]
    elif len(digits) == 10:
        number = DEFAULT_COUNTRY + digits
    elif len(digits) == 11 and digits.startswith("0"):
        number = DEFAULT_COUNTRY + digits[1:]
    elif len(digits) == 12 and digits.startswith(DEFAULT_COUNTRY):
        number = digits
    else:
        return None
    return f"+{number}" if 8 <= len(number) <= 15 else None


def mask_phone(number: str) -> str:
    """+91 ••••• ••210 style: enough for the owner to recognise it, not enough to copy."""
    return f"{number[:3]} ••••• ••{number[-3:]}" if len(number) > 6 else number


def _with_prefix(number: str) -> str:
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def post_form(url: str, headers: dict[str, str], form: dict[str, str], timeout: float = 20) -> dict:
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(form).encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json", "User-Agent": "EverestMills/1.0", **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (a fixed https address)
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except (ValueError, OSError):
            body = {}
        return {"error": True, "http": exc.code, "code": body.get("code"), "message": str(body.get("message") or "")[:250]}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"error": True, "http": 0, "message": "Could not reach WhatsApp"}
    except ValueError:
        return {"error": True, "http": 0, "message": "WhatsApp sent something unreadable"}


# Twilio error codes worth a plain explanation
_HINTS = {
    63016: "This phone has not joined the sandbox yet. On that phone, send the join code to the sandbox number first.",
    63015: "This phone has not joined the sandbox yet. On that phone, send the join code to the sandbox number first.",
    21211: "That does not look like a valid phone number.",
    21608: "This phone has not joined the sandbox yet. On that phone, send the join code to the sandbox number first.",
    21655: "Twilio does not know that template ID on your account. In Twilio open Try it out, Send a WhatsApp message, and copy the ContentSid (starts with HX) from its sample code.",
    21654: "Twilio needs this message sent as a template. In Twilio's Content Template Builder make a text template and paste its ID (starts with HX) into 'Message template ID' on this page.",
}


def _trial_hint(message: str) -> str | None:
    """Twilio's trial-account refusal for a destination, explained in steps the owner can follow."""
    if "trial" in message.lower() and ("verified" in message.lower() or "destination" in message.lower()):
        return ("Twilio will not send to this number from a trial account yet. On that phone, send the sandbox join code to the sandbox number; "
                "check the sender here is the sandbox number; and in Twilio under Messaging, Settings, Geo permissions, allow the country.")
    return None


def build_form(config: WhatsAppConfig, to_number: str, message: str, link: str | None) -> dict[str, str]:
    """What is posted to Twilio. With a template: the message and the link fill its two blanks ({{1}} and {{2}}).
    Without one: a plain text message, with the tracking link on a line of its own."""
    form = {"From": _with_prefix(config.from_number or ""), "To": _with_prefix(to_number)}
    if config.content_sid:
        form["ContentSid"] = config.content_sid
        form["ContentVariables"] = json.dumps({"1": message.strip(), "2": link or "the Everest Mills website"})
    else:
        form["Body"] = message.strip() + (f"\n\nTrack my order: {link}" if link else "")
    return form


def send_text(config: WhatsAppConfig, to_number: str, message: str, link: str | None = None, post: PostForm = post_form) -> SendResult:
    """Sends one WhatsApp message. Never raises: the result says what happened."""
    if not config.ready:
        return SendResult("skipped", "WhatsApp is not connected")
    auth = base64.b64encode(f"{config.account_sid}:{config.auth_token}".encode()).decode()
    reply = post(TWILIO_URL.format(sid=config.account_sid), {"Authorization": f"Basic {auth}"}, build_form(config, to_number, message, link), 20)
    if reply.get("error"):
        if reply.get("http") in (401, 403):
            return SendResult("failed", "WhatsApp refused the account details. Check the Account SID and Auth Token.")
        code = reply.get("code") or 0
        text = _HINTS.get(code) or _trial_hint(reply.get("message") or "") or reply.get("message") or f"WhatsApp refused the message ({reply.get('http')})"
        # Twilio's own error number is kept, so the exact cause can be looked up
        return SendResult("failed", f"{text} (Twilio error {code})" if code else text)
    if reply.get("error_code"):
        code = int(reply["error_code"])
        text = _HINTS.get(code) or _trial_hint(str(reply.get("error_message") or "")) or str(reply.get("error_message") or "WhatsApp refused the message")
        return SendResult("failed", f"{text} (Twilio error {code})", reply.get("sid"))
    return SendResult("sent", None, reply.get("sid"))


def tracking_text(message: str, public_url: str | None, order_code: str) -> str:
    """The message as it goes out on WhatsApp: the sentence, then a link to follow the order, as in the shop apps."""
    text = message.strip()
    if public_url:
        text += f"\n\nTrack my order: {public_url.rstrip('/')}/portal/orders/{order_code}"
    return text
