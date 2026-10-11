"""WhatsApp: a delay notice goes to the buyer's bell and, when the mill has connected a Twilio account, to their WhatsApp."""
import base64
import json
import urllib.error

import pytest

from app.core.auth import COOKIE_NAME, create_token
from app.modules.llm import crypto
from app.modules.notices import service, whatsapp
from app.modules.notices.whatsapp import WhatsAppConfig, mask_phone, normalise_phone, send_text, tracking_text
from tests.factories import make_buyer, make_order, make_user

READY = WhatsAppConfig("ACtest123", "secret-token-value", "+14155238886", "https://mill.example", True)


# ---------- phone numbers ----------

@pytest.mark.parametrize("raw,expected", [
    ("98450 12345", "+919845012345"), ("098450-12345", "+919845012345"), ("919845012345", "+919845012345"),
    ("+91 98450 12345", "+919845012345"), ("0091 98450 12345", "+919845012345"), ("(+44) 7700 900123", "+447700900123"),
    ("+1 415 523 8886", "+14155238886")])
def test_phone_numbers_become_international_form(raw, expected):
    assert normalise_phone(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "12345", "call me", "+12", "+1234567890123456789"])
def test_things_that_cannot_be_a_phone_number_are_refused(raw):
    assert normalise_phone(raw) is None


def test_a_number_is_masked_for_display():
    assert mask_phone("+919845012345") == "+91 ••••• ••345" and mask_phone("+1234") == "+1234"


def test_the_tracking_link_follows_the_message():
    assert tracking_text("Delayed.", "https://mill.example/", "ORD-0001") == "Delayed.\n\nTrack my order: https://mill.example/portal/orders/ORD-0001"
    assert tracking_text(" Delayed. ", None, "ORD-0001") == "Delayed."


# ---------- sending through Twilio ----------

def test_a_message_is_posted_to_twilio_with_the_account_and_whatsapp_prefixes():
    seen = {}

    def post(url, headers, form, timeout):
        seen.update(url=url, headers=headers, form=form)
        return {"sid": "SM123", "status": "queued"}

    r = send_text(READY, "+919845012345", "Hello", post=post)
    assert r.status == "sent" and r.sid == "SM123" and r.detail is None
    assert seen["url"] == "https://api.twilio.com/2010-04-01/Accounts/ACtest123/Messages.json"
    assert seen["form"] == {"From": "whatsapp:+14155238886", "To": "whatsapp:+919845012345", "Body": "Hello"}
    assert base64.b64decode(seen["headers"]["Authorization"].split()[1]).decode() == "ACtest123:secret-token-value"


def test_nothing_is_sent_when_whatsapp_is_not_connected():
    called = []
    r = send_text(WhatsAppConfig(None, None, None, None, False), "+919845012345", "Hi", post=lambda *a: called.append(a) or {})
    assert r.status == "skipped" and called == []


@pytest.mark.parametrize("reply,expect", [
    ({"error": True, "http": 401, "message": "Authenticate"}, "Check the Account SID and Auth Token"),
    ({"error": True, "http": 400, "code": 63016, "message": "x"}, "has not joined the sandbox"),
    ({"error": True, "http": 400, "code": 21211, "message": "x"}, "valid phone number"),
    ({"error": True, "http": 500, "message": "Server trouble"}, "Server trouble"),
    ({"error": True, "http": 0, "message": "Could not reach WhatsApp"}, "Could not reach WhatsApp"),
    ({"sid": "SM1", "error_code": 63016, "error_message": "x"}, "has not joined the sandbox")])
def test_a_refusal_comes_back_as_words_the_owner_can_act_on_and_never_the_token(reply, expect):
    r = send_text(READY, "+919845012345", "Hi", post=lambda *a: reply)
    assert r.status == "failed" and expect in r.detail and "secret-token-value" not in (r.detail or "")


def test_the_real_transport_turns_http_errors_into_a_plain_reply(monkeypatch):
    import io

    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 400, "Bad", {}, io.BytesIO(json.dumps({"code": 63016, "message": "not joined"}).encode()))

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    reply = whatsapp.post_form("https://api.twilio.com/x", {}, {"a": "b"})
    assert reply["error"] is True and reply["code"] == 63016 and reply["http"] == 400

    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("down")))
    assert whatsapp.post_form("https://api.twilio.com/x", {}, {"a": "b"})["message"] == "Could not reach WhatsApp"


# ---------- the connection settings (owner) ----------

BODY = {"account_sid": "ACtest123", "auth_token": "secret-token-value", "from_number": "whatsapp:+1 415 523 8886", "public_url": "https://mill.example/", "enabled": True}


def test_before_anything_is_saved_whatsapp_is_off(client, login_as):
    login_as("owner")
    assert client.get("/api/messaging/settings").json() == {"account_sid": None, "token_set": False, "from_number": None, "content_sid": None, "public_url": None, "enabled": False, "ready": False}


def test_saving_stores_the_token_encrypted_and_never_returns_it(client, login_as, db):
    login_as("owner")
    r = client.put("/api/messaging/settings", json=BODY)
    assert r.status_code == 200
    assert r.json() == {"account_sid": "ACtest123", "token_set": True, "from_number": "+14155238886", "content_sid": None, "public_url": "https://mill.example", "enabled": True, "ready": True}
    assert "secret-token-value" not in json.dumps(r.json())
    from app.db.models import MessagingSettings
    row = db.get(MessagingSettings, 1)
    assert row.auth_token_encrypted and "secret-token-value" not in row.auth_token_encrypted
    assert crypto.decrypt_key(row.auth_token_encrypted) == "secret-token-value"


def test_leaving_the_token_out_keeps_the_saved_one_and_an_empty_one_removes_it(client, login_as):
    login_as("owner")
    client.put("/api/messaging/settings", json=BODY)
    keep = client.put("/api/messaging/settings", json={"account_sid": "ACtest123", "enabled": True})
    assert keep.json()["token_set"] is True and keep.json()["ready"] is True
    gone = client.put("/api/messaging/settings", json={"auth_token": "", "enabled": False})
    assert gone.json()["token_set"] is False and gone.json()["ready"] is False


def test_it_cannot_be_switched_on_with_details_missing(client, login_as):
    login_as("owner")
    r = client.put("/api/messaging/settings", json={"account_sid": "ACtest123", "enabled": True})
    assert r.status_code == 422 and r.json()["field"] == "enabled"


@pytest.mark.parametrize("patch,field", [({"from_number": "not a number"}, "from_number"), ({"public_url": "ftp://x"}, "public_url")])
def test_a_bad_sender_or_address_is_refused(client, login_as, patch, field):
    login_as("owner")
    r = client.put("/api/messaging/settings", json={**BODY, **patch})
    assert r.status_code == 422 and r.json()["field"] == field


@pytest.mark.parametrize("role", ["accountant", "supervisor", "store", "qc", "dispatch", "buyer"])
def test_only_the_owner_touches_the_connection(client, login_as, role):
    login_as(role)
    assert client.get("/api/messaging/settings").status_code == 403
    assert client.put("/api/messaging/settings", json=BODY).status_code == 403
    assert client.post("/api/messaging/test", json={"to": "+919845012345"}).status_code == 403


def test_the_test_message_goes_to_the_number_given(client, login_as, monkeypatch):
    login_as("owner")
    client.put("/api/messaging/settings", json=BODY)
    sent = []
    monkeypatch.setattr(whatsapp, "send_text", lambda config, to, message, link=None, post=None: sent.append((to, message)) or whatsapp.SendResult("sent", None, "SM9"))
    r = client.post("/api/messaging/test", json={"to": "98450 12345"})
    assert r.json() == {"status": "sent", "detail": None, "to": "+91 ••••• ••345"} and sent[0][0] == "+919845012345"


def test_a_test_to_a_bad_number_is_refused(client, login_as):
    login_as("owner")
    assert client.post("/api/messaging/test", json={"to": "hello"}).status_code == 422


# ---------- a delay notice on WhatsApp ----------

@pytest.fixture
def connected(client, login_as):
    owner = login_as("owner")
    client.put("/api/messaging/settings", json=BODY)
    return owner


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    def fake(config, to, message, link=None, post=None):
        sent.append({"to": to, "message": message, "link": link})
        return whatsapp.SendResult("sent", None, "SM1")

    monkeypatch.setattr(whatsapp, "send_text", fake)
    return sent


def test_a_notice_goes_to_the_bell_and_to_whatsapp_with_the_tracking_link(client, connected, db, outbox):
    buyer = make_buyer(db, phone="98450 12345")
    order = make_order(db, buyer=buyer)
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "power_cut", "message": "Your order is late: a power cut."})
    assert r.status_code == 201 and r.json()["whatsapp_status"] == "sent" and r.json()["whatsapp_detail"] is None
    assert outbox == [{"to": "+919845012345", "message": "Your order is late: a power cut.", "link": f"https://mill.example/portal/orders/{order.code}"}]
    client.cookies.set(COOKIE_NAME, create_token(make_user(db, role="buyer", buyer_id=buyer.id).id))
    assert client.get("/api/portal/notifications").json()["unread"] == 1


def test_a_buyer_with_no_phone_still_gets_the_bell_notice(client, connected, db, outbox):
    order = make_order(db, buyer=make_buyer(db, phone=None))
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "Delayed."})
    assert r.status_code == 201 and r.json()["whatsapp_status"] == "skipped" and "no phone number" in r.json()["whatsapp_detail"] and outbox == []


def test_a_whatsapp_failure_never_loses_the_bell_notice(client, connected, db, monkeypatch):
    buyer = make_buyer(db, phone="98450 12345")
    order = make_order(db, buyer=buyer)
    monkeypatch.setattr(whatsapp, "send_text", lambda *a, **k: whatsapp.SendResult("failed", "This phone has not joined the sandbox yet."))
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "Delayed."})
    assert r.status_code == 201 and r.json()["whatsapp_status"] == "failed" and "sandbox" in r.json()["whatsapp_detail"]
    client.cookies.set(COOKIE_NAME, create_token(make_user(db, role="buyer", buyer_id=buyer.id).id))
    assert client.get("/api/portal/notifications").json()["items"][0]["whatsapp_status"] == "failed"


def test_without_a_connection_the_notice_says_it_was_not_sent_on_whatsapp(client, login_as, db, outbox):
    login_as("owner")
    order = make_order(db, buyer=make_buyer(db, phone="98450 12345"))
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "Delayed."})
    assert r.json()["whatsapp_status"] == "skipped" and "switched off" in r.json()["whatsapp_detail"] and outbox == []


def test_the_draft_tells_the_owner_where_it_would_go_or_why_not(client, connected, db):
    good = make_order(db, buyer=make_buyer(db, name="Sharma", phone="98450 12345"))
    r = client.post(f"/api/orders/{good.code}/delay-notice/draft", json={"reason": "other"}).json()["channel"]
    assert r == {"whatsapp_ready": True, "to": "+91 ••••• ••345", "phone": "919845012345", "problem": None, "tracking_url": f"https://mill.example/portal/orders/{good.code}"}
    none = make_order(db, buyer=make_buyer(db, name="NoPhone Co", phone=None))
    assert "no phone number" in client.post(f"/api/orders/{none.code}/delay-notice/draft", json={"reason": "other"}).json()["channel"]["problem"]
    odd = make_order(db, buyer=make_buyer(db, name="Odd Co", phone="abc"))
    assert "does not look right" in client.post(f"/api/orders/{odd.code}/delay-notice/draft", json={"reason": "other"}).json()["channel"]["problem"]


def test_the_buyers_phone_is_never_sent_to_the_buyer_or_shown_in_full(client, connected, db, outbox):
    buyer = make_buyer(db, phone="98450 12345")
    order = make_order(db, buyer=buyer)
    draft = client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "other"}).json()
    assert "98450" not in draft["channel"]["to"] and draft["channel"]["phone"] == "919845012345"  # masked for display; the digits are for the link


def test_twilios_own_error_number_is_kept_so_the_cause_can_be_looked_up():
    r = send_text(READY, "+916283828678", "Hi", post=lambda *a: {"error": True, "http": 400, "code": 21608, "message": "unverified"})
    assert r.status == "failed" and r.detail.endswith("(Twilio error 21608)")


def test_the_trial_account_refusal_is_explained_in_steps():
    reply = {"error": True, "http": 400, "code": 63015, "message": "No Twilio trial phone number is assigned for messaging to this destination number. Please add the 'to' number as a verified recipient."}
    r = send_text(READY, "+916283828678", "Hi", post=lambda *a: dict(reply, code=99999))
    assert "send the sandbox join code" in r.detail and "Geo permissions" in r.detail and "(Twilio error 99999)" in r.detail


# ---------- sending through a message template ----------

TEMPLATE = WhatsAppConfig("ACtest123", "secret-token-value", "+17372508034", "https://mill.example", True, "HX" + "a" * 32)


def test_without_a_template_the_message_is_plain_text_with_the_link_on_its_own_line():
    form = whatsapp.build_form(READY, "+919845012345", "  Delayed.  ", "https://mill.example/portal/orders/ORD-0001")
    assert form == {"From": "whatsapp:+14155238886", "To": "whatsapp:+919845012345", "Body": "Delayed.\n\nTrack my order: https://mill.example/portal/orders/ORD-0001"}


def test_with_a_template_the_message_and_the_link_fill_its_two_blanks():
    form = whatsapp.build_form(TEMPLATE, "+919845012345", " Delayed. ", "https://mill.example/portal/orders/ORD-0001")
    assert form["ContentSid"] == "HX" + "a" * 32 and "Body" not in form
    assert json.loads(form["ContentVariables"]) == {"1": "Delayed.", "2": "https://mill.example/portal/orders/ORD-0001"}
    assert json.loads(whatsapp.build_form(TEMPLATE, "+919845012345", "Hi", None)["ContentVariables"])["2"] == "the Everest Mills website"


def test_a_template_message_is_what_is_posted_to_twilio():
    seen = {}
    send_text(TEMPLATE, "+916282828678", "Delayed.", "https://x/y", post=lambda url, headers, form, timeout: seen.update(form) or {"sid": "SM5"})
    assert "ContentSid" in seen and "Body" not in seen


def test_the_content_sid_required_refusal_says_how_to_make_a_template():
    r = send_text(READY, "+919845012345", "Hi", post=lambda *a: {"error": True, "http": 400, "code": 21654, "message": "ContentSid Required"})
    assert "Content Template Builder" in r.detail and "(Twilio error 21654)" in r.detail


def test_the_template_id_is_saved_checked_and_can_be_cleared(client, login_as):
    login_as("owner")
    ok = client.put("/api/messaging/settings", json={**BODY, "content_sid": " HX" + "b" * 32 + " "})
    assert ok.status_code == 200 and ok.json()["content_sid"] == "HX" + "b" * 32
    bad = client.put("/api/messaging/settings", json={**BODY, "content_sid": "not-a-template"})
    assert bad.status_code == 422 and bad.json()["field"] == "content_sid"
    cleared = client.put("/api/messaging/settings", json={**BODY, "content_sid": ""})
    assert cleared.json()["content_sid"] is None


def test_an_unknown_template_id_says_where_to_find_the_right_one():
    r = send_text(TEMPLATE, "+916282828678", "Hi", post=lambda *a: {"error": True, "http": 400, "code": 21655, "message": "The ContentSid is Invalid"})
    assert "copy the ContentSid" in r.detail and "Try it out" in r.detail and r.detail.endswith("(Twilio error 21655)")
