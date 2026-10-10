"""Unit tests for the language-model module's parts: key encryption, provider adapters, the tool loop and the report card."""
import io
import json
import urllib.error

import pytest

from app.config import settings
from app.core.errors import AppError
from app.modules.llm import adapters, crypto, engine, reportcard
from app.modules.llm.adapters import AnthropicAdapter, OpenAICompatibleAdapter
from app.modules.llm.data import ToolContext
from app.modules.llm.tools import FINANCE, MANAGERS, BY_NAME, TOOLS, Tool, NoInput, OrderIn, tools_for
from app.modules.llm.types import AdapterError, Completion, ToolCall, ToolResult, ToolSpec, Turn


# ---------- key encryption ----------

def test_a_key_round_trips_and_is_not_stored_as_written():
    token = crypto.encrypt_key("sk-ant-secret-123")
    assert "secret" not in token and token != "sk-ant-secret-123"
    assert crypto.decrypt_key(token) == "sk-ant-secret-123"


def test_two_encryptions_of_the_same_key_differ():
    assert crypto.encrypt_key("k") != crypto.encrypt_key("k")


def test_a_key_cannot_be_read_after_the_secret_changes(monkeypatch):
    token = crypto.encrypt_key("sk-123")
    monkeypatch.setattr(settings, "llm_key_secret", "a-different-secret")
    assert crypto.decrypt_key(token) is None


def test_garbage_is_not_a_key():
    assert crypto.decrypt_key("not-a-token") is None


# ---------- Anthropic adapter ----------

class Recorder:
    """A stand-in for the network: remembers the request and returns a prepared reply."""

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload, timeout))
        return self.reply


SPEC = ToolSpec("get_stock", "Stock per yarn type", {"type": "object", "properties": {}})


def test_anthropic_sends_the_key_the_system_prompt_and_the_tools():
    rec = Recorder({"content": [{"type": "text", "text": "Hello"}]})
    out = AnthropicAdapter("sk-1", "claude-opus-5-5", post=rec).complete("Be brief", [Turn("user", "Hi")], [SPEC], {"max_tokens": 200})
    url, headers, payload, _ = rec.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "sk-1" and headers["anthropic-version"]
    assert payload["model"] == "claude-opus-5-5" and payload["system"] == "Be brief" and payload["max_tokens"] == 200
    assert payload["tools"] == [{"name": "get_stock", "description": "Stock per yarn type", "input_schema": SPEC.schema}]
    assert payload["messages"] == [{"role": "user", "content": "Hi"}]
    assert out.text == "Hello" and out.tool_calls == []


def test_anthropic_sends_no_tools_field_when_there_are_none():
    rec = Recorder({"content": [{"type": "text", "text": "ok"}]})
    AnthropicAdapter("k", "m", post=rec).complete("s", [Turn("user", "q")], [])
    assert "tools" not in rec.calls[0][2]


def test_anthropic_reads_tool_calls_and_sends_results_back_in_its_own_shape():
    rec = Recorder({"content": [{"type": "text", "text": "Let me look."}, {"type": "tool_use", "id": "t1", "name": "get_stock", "input": {}}]})
    adapter = AnthropicAdapter("k", "m", post=rec)
    out = adapter.complete("s", [Turn("user", "q")], [SPEC])
    assert out.text == "Let me look." and out.tool_calls == [ToolCall("t1", "get_stock", {})]
    turns = [Turn("user", "q"), Turn("assistant", "Let me look.", tool_calls=out.tool_calls),
             Turn("tool", tool_results=[ToolResult("t1", "get_stock", "[1]", is_error=False)])]
    adapter.complete("s", turns, [SPEC])
    messages = rec.calls[1][2]["messages"]
    assert messages[1]["content"] == [{"type": "text", "text": "Let me look."}, {"type": "tool_use", "id": "t1", "name": "get_stock", "input": {}}]
    assert messages[2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "[1]", "is_error": False}]}


# ---------- OpenAI-compatible adapter ----------

def test_openai_compatible_uses_the_base_url_and_a_bearer_key():
    rec = Recorder({"choices": [{"message": {"content": "Hi there"}}]})
    out = OpenAICompatibleAdapter("http://localhost:11434/v1/", "llama3", "sk-x", post=rec).complete("sys", [Turn("user", "Hi")], [SPEC])
    url, headers, payload, _ = rec.calls[0]
    assert url == "http://localhost:11434/v1/chat/completions"
    assert headers == {"Authorization": "Bearer sk-x"}
    assert payload["messages"][0] == {"role": "system", "content": "sys"}
    assert payload["tools"] == [{"type": "function", "function": {"name": "get_stock", "description": "Stock per yarn type", "parameters": SPEC.schema}}]
    assert out.text == "Hi there"


def test_openai_compatible_needs_no_key_for_a_local_server():
    rec = Recorder({"choices": [{"message": {"content": "ok"}}]})
    OpenAICompatibleAdapter("http://localhost:11434/v1", "llama3", None, post=rec).complete("s", [Turn("user", "q")], [])
    assert rec.calls[0][1] == {}
    assert "tools" not in rec.calls[0][2]


def test_openai_compatible_reads_tool_calls_and_sends_each_result_as_its_own_message():
    reply = {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_stock", "arguments": "{\"a\": 1}"}}]}}]}
    rec = Recorder(reply)
    adapter = OpenAICompatibleAdapter("http://x/v1", "m", "k", post=rec)
    out = adapter.complete("s", [Turn("user", "q")], [SPEC])
    assert out.text == "" and out.tool_calls == [ToolCall("c1", "get_stock", {"a": 1})]
    turns = [Turn("user", "q"), Turn("assistant", "", tool_calls=out.tool_calls),
             Turn("tool", tool_results=[ToolResult("c1", "get_stock", "r1"), ToolResult("c2", "get_x", "r2")])]
    adapter.complete("s", turns, [SPEC])
    messages = rec.calls[1][2]["messages"]
    assert messages[2]["tool_calls"][0]["function"]["arguments"] == "{\"a\": 1}"
    assert messages[3:] == [{"role": "tool", "tool_call_id": "c1", "content": "r1"}, {"role": "tool", "tool_call_id": "c2", "content": "r2"}]


def test_openai_compatible_survives_broken_tool_arguments():
    reply = {"choices": [{"message": {"tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_stock", "arguments": "{oops"}}]}}]}
    out = OpenAICompatibleAdapter("http://x/v1", "m", post=Recorder(reply)).complete("s", [Turn("user", "q")], [SPEC])
    assert out.tool_calls[0].arguments == {}


@pytest.mark.parametrize("reply", [{}, {"choices": []}, {"choices": [{}]}, {"choices": None}])
def test_openai_compatible_rejects_an_unexpected_shape(reply):
    with pytest.raises(AdapterError) as e:
        OpenAICompatibleAdapter("http://x/v1", "m", post=Recorder(reply)).complete("s", [Turn("user", "q")], [])
    assert e.value.kind == "server"


# ---------- the HTTP call itself ----------

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body))


def test_post_json_returns_the_reply(monkeypatch):
    monkeypatch.setattr(adapters.urllib.request, "urlopen", lambda req, timeout: FakeResponse(b'{"ok": true}'))
    assert adapters.post_json("http://x", {}, {"a": 1}) == {"ok": True}


@pytest.mark.parametrize("code,kind", [(401, "auth"), (403, "auth"), (400, "bad_request"), (404, "bad_request"), (429, "bad_request"), (500, "server"), (503, "server")])
def test_post_json_says_why_the_provider_refused(monkeypatch, code, kind):
    def boom(req, timeout):
        raise http_error(code, b'{"error": {"message": "model not found"}}')
    monkeypatch.setattr(adapters.urllib.request, "urlopen", boom)
    with pytest.raises(AdapterError) as e:
        adapters.post_json("http://x", {"x-api-key": "sk-secret"}, {})
    assert e.value.kind == kind and "sk-secret" not in e.value.message


def test_a_bad_request_passes_on_the_providers_reason(monkeypatch):
    def boom(req, timeout):
        raise http_error(400, b'{"error": {"message": "model not found"}}')
    monkeypatch.setattr(adapters.urllib.request, "urlopen", boom)
    with pytest.raises(AdapterError) as e:
        adapters.post_json("http://x", {}, {})
    assert e.value.message == "model not found"


@pytest.mark.parametrize("exc", [urllib.error.URLError("no route"), TimeoutError(), ConnectionResetError()])
def test_post_json_reports_an_unreachable_provider(monkeypatch, exc):
    def boom(req, timeout):
        raise exc
    monkeypatch.setattr(adapters.urllib.request, "urlopen", boom)
    with pytest.raises(AdapterError) as e:
        adapters.post_json("http://x", {}, {})
    assert e.value.kind == "unreachable"


def test_post_json_reports_an_unreadable_reply(monkeypatch):
    monkeypatch.setattr(adapters.urllib.request, "urlopen", lambda req, timeout: FakeResponse(b"<html>nope</html>"))
    with pytest.raises(AdapterError) as e:
        adapters.post_json("http://x", {}, {})
    assert e.value.kind == "server"


# ---------- which tools a role gets ----------

def names(role, feature):
    return {t.name for t in tools_for(role, feature)}


def test_owner_and_accountant_get_the_money_tools_but_a_supervisor_does_not():
    for role in ("owner", "accountant"):
        assert {"get_order_cost", "get_month_summary", "get_machine_utilisation"} <= names(role, "copilot")
    assert not ({"get_order_cost", "get_month_summary", "get_machine_utilisation"} & names("supervisor", "copilot"))
    assert {"get_stock", "get_late_orders", "get_order_status"} <= names("supervisor", "copilot")


def test_roles_outside_the_managers_get_no_copilot_tools():
    for role in ("store", "qc", "dispatch", "buyer"):
        assert names(role, "copilot") == set()


def test_a_buyer_gets_only_their_own_tools_and_none_takes_a_buyer_id():
    assert names("buyer", "buyer") == {"get_my_orders", "get_my_order_status", "get_my_order_eta"}
    assert names("owner", "buyer") == set()
    for t in tools_for("buyer", "buyer"):
        assert "buyer_id" not in json.dumps(t.spec().schema)


def test_every_tool_has_a_schema_and_a_description():
    assert len(TOOLS) == len(BY_NAME)
    for t in TOOLS:
        spec = t.spec()
        assert spec.description and spec.schema["type"] == "object" and "title" not in spec.schema
        assert t.roles <= {"owner", "accountant", "supervisor", "buyer"}


def test_the_month_tools_only_accept_a_real_month():
    schema = BY_NAME["get_month_summary"].spec().schema
    assert "pattern" in json.dumps(schema)


# ---------- the tool loop ----------

class Script:
    """A fake provider that replies from a list and remembers what it was asked."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, turns, tools, options=None):
        self.calls.append({"system": system, "turns": [Turn(t.role, t.text, list(t.tool_calls), list(t.tool_results)) for t in turns], "tools": [t.name for t in tools]})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def say(text):
    return Completion(text, [])


def call(name, args=None, id="c1"):
    return Completion("", [ToolCall(id, name, args or {})])


def fake_tool(name="get_thing", result=None, roles=MANAGERS, model=NoInput):
    return Tool(name, "a test tool", model, roles, "copilot", lambda ctx, args: result if result is not None else {"value": 42})


CTX = ToolContext(db=None, user=None)  # type: ignore[arg-type]


def test_a_question_that_needs_no_tool_is_answered_straight_away():
    adapter = Script(say("Hello."))
    result = engine.run_chat(adapter, "sys", [], "Hi", [fake_tool()], CTX)
    assert result.text == "Hello." and result.sources == []
    assert adapter.calls[0]["system"].startswith("sys ") and adapter.calls[0]["tools"] == ["get_thing"]


def test_the_model_is_told_todays_date_in_india_so_this_month_means_something():
    import datetime as dt
    assert engine.with_today("Be brief.", dt.date(2026, 10, 10)) == "Be brief. Today is 2026-10-10 (India time), so this month is 2026-10."
    adapter = Script(say("ok"))
    engine.run_chat(adapter, "sys", [], "q", [], CTX)
    assert "Today is " in adapter.calls[0]["system"] and "this month is " in adapter.calls[0]["system"]


def test_the_model_asks_for_a_tool_gets_the_result_and_answers_from_it():
    adapter = Script(call("get_thing"), say("It is 42."))
    result = engine.run_chat(adapter, "sys", [], "What is it?", [fake_tool()], CTX)
    assert result.text == "It is 42."
    assert [s.tool for s in result.sources] == ["get_thing"]
    assert result.sources[0].summary == '{"value": 42}'
    second = adapter.calls[1]["turns"]
    assert [t.role for t in second] == ["user", "assistant", "tool"]
    assert second[2].tool_results[0].content == '{"value": 42}' and not second[2].tool_results[0].is_error


def test_earlier_conversation_is_sent_before_the_new_question():
    adapter = Script(say("ok"))
    engine.run_chat(adapter, "s", [Turn("user", "first"), Turn("assistant", "answer")], "second", [], CTX)
    assert [t.text for t in adapter.calls[0]["turns"]] == ["first", "answer", "second"]


def test_the_sources_record_the_inputs_the_tool_was_called_with():
    adapter = Script(call("get_order", {"order_code": " ORD-0012 "}), say("done"))
    tool = fake_tool("get_order", model=OrderIn)
    result = engine.run_chat(adapter, "s", [], "q", [tool], CTX)
    assert result.sources[0].input == {"order_code": "ORD-0012"}


def test_several_tool_calls_in_one_turn_are_all_run():
    adapter = Script(Completion("", [ToolCall("a", "get_thing", {}), ToolCall("b", "get_thing", {})]), say("both"))
    result = engine.run_chat(adapter, "s", [], "q", [fake_tool()], CTX)
    assert len(result.sources) == 2
    assert len(adapter.calls[1]["turns"][2].tool_results) == 2


def test_a_tool_outside_the_roles_list_cannot_be_run_even_if_the_model_asks():
    adapter = Script(call("get_order_cost", {"order_code": "ORD-1"}), say("sorry"))
    result = engine.run_chat(adapter, "s", [], "q", [fake_tool()], CTX)
    sent_back = adapter.calls[1]["turns"][2].tool_results[0]
    assert sent_back.is_error and "not available" in sent_back.content
    assert result.sources[0].summary == "Not available" and result.text == "sorry"


def test_bad_tool_input_is_told_to_the_model_so_it_can_try_again():
    adapter = Script(call("get_order", {"order_code": ""}), call("get_order", {"order_code": "ORD-1"}), say("fixed"))
    result = engine.run_chat(adapter, "s", [], "q", [fake_tool("get_order", model=OrderIn)], CTX)
    first = adapter.calls[1]["turns"][2].tool_results[0]
    assert first.is_error and first.content.startswith("Invalid input")
    assert result.text == "fixed" and len(result.sources) == 2


def test_a_tool_that_fails_gives_the_model_the_reason():
    def fails(ctx, args):
        raise AppError("NOT_FOUND", "No such order", status=404)
    tool = Tool("get_thing", "t", NoInput, MANAGERS, "copilot", fails)
    adapter = Script(call("get_thing"), say("There is no such order."))
    result = engine.run_chat(adapter, "s", [], "q", [tool], CTX)
    back = adapter.calls[1]["turns"][2].tool_results[0]
    assert back.is_error and back.content == "No such order"
    assert result.sources[0].summary == "No such order"


def test_a_very_long_result_is_cut_before_it_goes_to_the_model():
    adapter = Script(call("get_thing"), say("ok"))
    result = engine.run_chat(adapter, "s", [], "q", [fake_tool(result={"big": "x" * 20000})], CTX)
    assert len(adapter.calls[1]["turns"][2].tool_results[0].content) == engine.RESULT_LIMIT
    assert len(result.sources[0].summary) <= engine.SUMMARY_LIMIT


def test_the_loop_stops_after_six_steps():
    adapter = Script(*[call("get_thing", id=f"c{i}") for i in range(10)])
    result = engine.run_chat(adapter, "s", [], "q", [fake_tool()], CTX)
    assert len(adapter.calls) == engine.MAX_STEPS == 6
    assert "could not finish" in result.text and len(result.sources) == 6


@pytest.mark.parametrize("kind", ["unreachable", "auth", "server"])
def test_a_provider_failure_becomes_ai_unavailable(kind):
    adapter = Script(AdapterError(kind, "boom"))
    with pytest.raises(AppError) as e:
        engine.run_chat(adapter, "s", [], "q", [], CTX)
    assert e.value.code == "AI_UNAVAILABLE" and e.value.status == 503 and "Check Settings" in e.value.message
    assert len(adapter.calls) == 1  # these are not retried


def test_a_refused_request_is_tried_once_more_then_reported():
    adapter = Script(AdapterError("bad_request", "bad tool call"), AdapterError("bad_request", "bad tool call"))
    with pytest.raises(AppError) as e:
        engine.run_chat(adapter, "s", [], "q", [], CTX)
    assert e.value.code == "AI_UNAVAILABLE" and "bad tool call" in e.value.message and len(adapter.calls) == 2


def test_a_refused_request_that_works_the_second_time_is_answered():
    adapter = Script(AdapterError("bad_request", "bad tool call"), say("Fine."))
    assert engine.run_chat(adapter, "s", [], "q", [], CTX).text == "Fine."


def test_requests_carry_a_plain_user_agent(monkeypatch):
    import io
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["ua"] = request.get_header("User-agent")
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    from app.modules.llm.adapters import post_json
    assert post_json("https://example.test/v1", {}, {}, 5) == {"ok": True}
    assert seen["ua"] == "EverestMills/1.0"


def test_an_empty_answer_gets_a_plain_fallback():
    assert engine.run_chat(Script(say("")), "s", [], "q", [], CTX).text == "I could not find an answer."


def test_the_prompts_forbid_guessing_numbers():
    for prompt in (engine.COPILOT_SYSTEM, engine.BUYER_SYSTEM):
        assert "never" in prompt.lower() and "tool" in prompt.lower()
    assert "costs" in engine.BUYER_SYSTEM and "other buyers" in engine.BUYER_SYSTEM


# ---------- the report card ----------

def test_numbers_are_read_with_commas_and_rupee_signs_ignored():
    assert reportcard.numbers_in("Profit was ₹1,98,500.50 and 3 days late, -2 left") == [198500.5, 3.0, -2.0]


def test_a_number_matches_to_the_paisa_but_not_loosely():
    q = reportcard.Question("q", numbers=[587.5])
    assert reportcard.passes(q, "There are 587.5 kg free.")
    assert reportcard.passes(q, "About 587.50 kg")
    assert not reportcard.passes(q, "About 587 kg")
    assert not reportcard.passes(q, "I do not know")


def test_every_listed_number_must_appear_but_only_one_of_the_alternatives():
    both = reportcard.Question("q", numbers=[1, 2])
    assert reportcard.passes(both, "1 and 2") and not reportcard.passes(both, "1 only")
    either = reportcard.Question("q", any_numbers=[45, 0.45])
    assert reportcard.passes(either, "45%") and reportcard.passes(either, "0.45") and not reportcard.passes(either, "46%")


def test_words_match_whole_words_only():
    yes = reportcard.Question("q", any_words=["yes"])
    assert reportcard.passes(yes, "Yes, it is.") and not reportcard.passes(yes, "My eyes hurt")
    assert reportcard.passes(reportcard.Question("q", words=["weaving"]), "It is held up in Weaving.")


def test_dates_are_accepted_in_the_ways_people_write_them():
    q = reportcard.Question("q", any_words=reportcard._date_forms("2026-10-20"))
    for answer in ("2026-10-20", "due 20 Oct", "20 October 2026", "October 20"):
        assert reportcard.passes(q, answer), answer
    assert not reportcard.passes(q, "21 Oct")


def test_what_was_expected_is_written_out_for_a_failed_line():
    assert reportcard.Question("q", numbers=[587.5], words=["weaving"], any_numbers=[45, 0.45]).expected() == "587.5; weaving; 45 or 0.45"


def test_the_questions_come_from_the_current_data_and_there_are_at_most_fifteen(client, login_as, db):
    user = login_as("owner")
    qs = reportcard.build_questions(ToolContext(db, user))
    assert 8 <= len(qs) <= 15
    assert all(q.numbers or q.any_numbers or q.words or q.any_words for q in qs)


def test_a_data_source_that_fails_only_removes_its_own_questions(client, login_as, db, monkeypatch):
    from tests.factories import make_lot

    user = login_as("owner")
    make_lot(db)        # stock is real data now: without a lot there is no stock row, so no stock questions to remove
    full = len(reportcard.build_questions(ToolContext(db, user)))
    monkeypatch.setattr("app.modules.llm.data.stock", lambda ctx: (_ for _ in ()).throw(RuntimeError("down")))
    fewer = reportcard.build_questions(ToolContext(db, user))
    assert 0 < len(fewer) < full


# ---------- listing models ----------

def test_the_openai_compatible_adapter_lists_model_names_with_the_key_as_a_bearer_token():
    seen = {}

    def get(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return {"data": [{"id": "zeta"}, {"id": "alpha"}, {"id": "alpha"}, {"nope": 1}]}

    adapter = OpenAICompatibleAdapter("https://api.groq.com/openai/v1/", "m", "gsk-x", get=get)
    assert adapter.models() == ["alpha", "zeta"]
    assert seen["url"] == "https://api.groq.com/openai/v1/models" and seen["headers"] == {"Authorization": "Bearer gsk-x"}


def test_the_anthropic_adapter_lists_model_names_with_its_headers():
    seen = {}

    def get(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return {"data": [{"id": "claude-b"}, {"id": "claude-a"}]}

    adapter = AnthropicAdapter("sk-1", "m", get=get)
    assert adapter.models() == ["claude-a", "claude-b"]
    assert seen["url"].startswith("https://api.anthropic.com/v1/models") and seen["headers"]["x-api-key"] == "sk-1"


def test_a_model_list_in_an_unexpected_shape_is_empty_not_a_crash():
    assert OpenAICompatibleAdapter("http://x/v1", "m", get=lambda *a: {"oops": True}).models() == []


def test_a_missing_model_is_reported_with_what_the_provider_said(monkeypatch):
    import io
    import urllib.error

    def refuse(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO(b'{"error": {"message": "The model `x` does not exist"}}'))

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(AdapterError) as e:
        adapters.post_json("https://api.example.test/v1/chat/completions", {}, {}, 5)
    assert e.value.kind == "bad_request" and "The model `x` does not exist" in e.value.message and "/v1" in e.value.message
