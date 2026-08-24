"""The Claude and Ollama integrations.

The Anthropic path is exercised against a real local HTTP server speaking real
server-sent events, not a mocked urlopen. The parser is the part that can be
subtly wrong — an SSE stream is line-oriented text with two interleaved kinds
of line and a JSON payload that repeats its own type — and a mock built from
the same assumptions as the parser proves nothing about either.

No test here contacts api.anthropic.com.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


# ─── a stub that speaks the real wire format ───────────────────────────

def _sse(events):
    """Encode events the way the API does: an `event:` line naming the type,
    a `data:` line carrying JSON, and a blank line between records."""
    out = []
    for e in events:
        out.append(f"event: {e['type']}")
        out.append(f"data: {json.dumps(e)}")
        out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")


def _text_stream(chunks, stop_reason="end_turn"):
    events = [{"type": "message_start", "message": {"id": "msg_1"}},
              {"type": "content_block_start", "index": 0,
               "content_block": {"type": "text", "text": ""}}]
    for c in chunks:
        events.append({"type": "content_block_delta", "index": 0,
                       "delta": {"type": "text_delta", "text": c}})
    events += [{"type": "content_block_stop", "index": 0},
               {"type": "message_delta", "delta": {"stop_reason": stop_reason},
                "usage": {"output_tokens": 12}},
               {"type": "message_stop"}]
    return _sse(events)


class _StubAPI:
    """A one-connection HTTP server standing in for api.anthropic.com."""

    def __init__(self, body=b"", status=200, content_type="text/event-stream"):
        self.body, self.status, self.content_type = body, status, content_type
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.requests.append({
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(self.rfile.read(n) or b"{}"),
                })
                self.send_response(outer.status)
                self.send_header("Content-Type", outer.content_type)
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1/messages"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def stub():
    made = []

    def _make(**kw):
        s = _StubAPI(**kw)
        made.append(s)
        return s

    yield _make
    for s in made:
        s.close()


def _run(ffmod, chef, monkeypatch, stub_server, prompt="make a recipe"):
    """Point the Claude path at the stub and collect what the callbacks see."""
    real_request = ffmod.urllib.request.Request

    def _redirect(url, *a, **kw):
        return real_request(stub_server.url, *a, **kw)

    monkeypatch.setattr(ffmod.urllib.request, "Request", _redirect)
    chunks, errors, done = [], [], []

    def on_chunk(t):
        (done if t is None else chunks).append(t)

    chef._anthropic_generate(prompt, on_chunk, errors.append)
    return "".join(chunks), errors, done


@pytest.fixture
def chef(ffmod):
    c = ffmod.AIChef.__new__(ffmod.AIChef)      # skip __init__: no config read
    c.provider = "anthropic"
    c.anthropic_key = "sk-ant-test"
    c.anthropic_model = ffmod.DEFAULT_CLAUDE_MODEL
    c.ollama_url = "http://localhost:11434"
    c.ollama_model = "qwen2.5:14b"
    c.retired_model = ""
    return c


# ─── the model pin ─────────────────────────────────────────────────────

def test_the_default_model_is_a_current_one(ffmod):
    """v3.0 shipped claude-sonnet-4-20250514, which had been superseded three
    model generations over. Nothing in the code could notice."""
    assert ffmod.DEFAULT_CLAUDE_MODEL in {m[1] for m in ffmod.CLAUDE_MODELS}
    assert "2025" not in ffmod.DEFAULT_CLAUDE_MODEL, (
        "a dated snapshot id will go stale; use the undated alias")


def test_the_model_roster_is_well_formed(ffmod):
    assert len(ffmod.CLAUDE_MODELS) >= 2
    for label, model_id, note in ffmod.CLAUDE_MODELS:
        assert label and model_id and note
        assert model_id.startswith("claude-")


def test_a_retired_model_in_a_saved_config_is_migrated(ffmod, tmp_path, monkeypatch):
    """Someone upgrading from 3.0 has claude-sonnet-4-20250514 in their config.
    Left alone it would 404 on the first generation with no explanation."""
    cfg = tmp_path / ".flavorforge_config.json"
    cfg.write_text(json.dumps({"anthropic_model": "claude-sonnet-4-20250514",
                               "anthropic_key": "sk-ant-x"}), encoding="utf-8")
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path))
    c = ffmod.AIChef()
    assert c.anthropic_model == ffmod.DEFAULT_CLAUDE_MODEL
    assert c.retired_model == "claude-sonnet-4-20250514"
    assert c.anthropic_key == "sk-ant-x", "migration must not lose the key"


def test_a_current_model_in_a_saved_config_is_left_alone(ffmod, tmp_path, monkeypatch):
    cfg = tmp_path / ".flavorforge_config.json"
    keep = ffmod.CLAUDE_MODELS[-1][1]
    cfg.write_text(json.dumps({"anthropic_model": keep}), encoding="utf-8")
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path))
    c = ffmod.AIChef()
    assert c.anthropic_model == keep and c.retired_model == ""


# ─── streaming ─────────────────────────────────────────────────────────

def test_the_request_asks_for_a_stream(ffmod, chef, monkeypatch, stub):
    s = stub(body=_text_stream(["hi"]))
    _run(ffmod, chef, monkeypatch, s)
    body = s.requests[0]["body"]
    assert body["stream"] is True
    assert body["model"] == ffmod.DEFAULT_CLAUDE_MODEL
    assert body["max_tokens"] == ffmod.CLAUDE_MAX_TOKENS
    assert body["messages"] == [{"role": "user", "content": "make a recipe"}]


def test_the_api_version_and_key_headers_are_sent(ffmod, chef, monkeypatch, stub):
    s = stub(body=_text_stream(["hi"]))
    _run(ffmod, chef, monkeypatch, s)
    h = {k.lower(): v for k, v in s.requests[0]["headers"].items()}
    assert h["x-api-key"] == "sk-ant-test"
    assert h["anthropic-version"] == "2023-06-01"


def test_text_arrives_in_order_and_in_pieces(ffmod, chef, monkeypatch, stub):
    """The user-visible payoff: the recipe types itself out instead of
    appearing all at once after a 30-second spinner, which is what the old
    blocking read did while Ollama streamed."""
    s = stub(body=_text_stream(["DISH NAME: ", "Char Siu ", "Pork"]))
    text, errors, done = _run(ffmod, chef, monkeypatch, s)
    assert text == "DISH NAME: Char Siu Pork"
    assert not errors
    assert done == [None], "must signal completion exactly once"


def test_a_truncated_response_says_so(ffmod, chef, monkeypatch, stub):
    """stop_reason was never inspected, so a recipe cut off at the token
    ceiling simply stopped mid-step and looked finished."""
    s = stub(body=_text_stream(["1. Sear the pork", "\n2. Add the "],
                               stop_reason="max_tokens"))
    text, errors, _ = _run(ffmod, chef, monkeypatch, s)
    assert "cut off" in text.lower()
    assert str(ffmod.CLAUDE_MAX_TOKENS) in text


def test_a_complete_response_says_nothing_extra(ffmod, chef, monkeypatch, stub):
    s = stub(body=_text_stream(["all done"]))
    text, _, _ = _run(ffmod, chef, monkeypatch, s)
    assert text == "all done"


def test_a_refusal_is_reported_as_an_error(ffmod, chef, monkeypatch, stub):
    s = stub(body=_text_stream(["..."], stop_reason="refusal"))
    _, errors, done = _run(ffmod, chef, monkeypatch, s)
    assert errors and "declined" in errors[0].lower()
    assert done == [], "a refusal must not also report success"


def test_a_mid_stream_error_event_is_surfaced(ffmod, chef, monkeypatch, stub):
    body = _sse([{"type": "message_start", "message": {}},
                 {"type": "error", "error": {"type": "overloaded_error",
                                             "message": "Overloaded"}}])
    s = stub(body=body)
    _, errors, done = _run(ffmod, chef, monkeypatch, s)
    assert errors and "overloaded" in errors[0].lower()
    assert done == []


def test_malformed_sse_lines_are_skipped_not_fatal(ffmod, chef, monkeypatch, stub):
    """A proxy or a partial flush can put anything on the wire."""
    good = _text_stream(["ok"])
    body = b": comment line\ndata: not json\ndata:\n\n" + good
    s = stub(body=body)
    text, errors, done = _run(ffmod, chef, monkeypatch, s)
    assert text == "ok" and not errors and done == [None]


def test_non_text_deltas_are_ignored(ffmod, chef, monkeypatch, stub):
    """Thinking blocks and tool-use deltas share the content_block_delta type;
    only text_delta carries recipe text."""
    body = _sse([
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "thinking_delta", "thinking": "hmm"}},
        {"type": "content_block_delta", "index": 0,
         "delta": {"type": "text_delta", "text": "visible"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}},
    ])
    s = stub(body=body)
    text, _, _ = _run(ffmod, chef, monkeypatch, s)
    assert text == "visible"


# ─── errors ────────────────────────────────────────────────────────────

def test_a_missing_key_is_reported_before_any_request(ffmod, chef, monkeypatch, stub):
    chef.anthropic_key = ""
    s = stub(body=_text_stream(["x"]))
    _, errors, _ = _run(ffmod, chef, monkeypatch, s)
    assert errors and "api key" in errors[0].lower()
    assert not s.requests, "should not have called the API at all"


@pytest.mark.parametrize("status,needle", [
    (401, "api key"),
    (404, "retired"),
    (429, "rate limited"),
])
def test_http_errors_carry_an_actionable_hint(ffmod, chef, monkeypatch, stub,
                                              status, needle):
    """"HTTP 401" alone tells a cook nothing. Each of these has exactly one
    likely cause and the message should name it."""
    s = stub(status=status, body=b'{"error":{"message":"nope"}}',
             content_type="application/json")
    _, errors, done = _run(ffmod, chef, monkeypatch, s)
    assert errors, f"HTTP {status} produced no error"
    assert needle in errors[0].lower(), errors[0]
    assert done == []


def test_an_unreachable_host_is_reported_not_raised(ffmod, chef, monkeypatch):
    """The generate() thread has no one to catch an exception, so anything
    escaping here is lost entirely."""
    real = ffmod.urllib.request.Request
    monkeypatch.setattr(ffmod.urllib.request, "Request",
                        lambda url, *a, **kw: real("http://127.0.0.1:1/x", *a, **kw))
    errors = []
    chef._anthropic_generate("p", lambda t: None, errors.append)
    assert errors


# ─── config persistence ────────────────────────────────────────────────

def test_saving_the_config_is_atomic(ffmod, tmp_path, monkeypatch):
    """A plain open("w") truncates first. A crash between truncate and write
    leaves an empty config — and this is the file holding the API key."""
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path))
    c = ffmod.AIChef()
    c.anthropic_key = "sk-ant-secret"
    assert c.save_config() is True
    saved = json.loads((tmp_path / ".flavorforge_config.json").read_text(encoding="utf-8"))
    assert saved["anthropic_key"] == "sk-ant-secret"
    assert not list(tmp_path.glob("*.tmp")), "temp file left behind"


def test_a_failed_save_leaves_no_temp_file(ffmod, tmp_path, monkeypatch):
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path))
    c = ffmod.AIChef()
    # json.dump is called with default=list, so anything iterable now encodes.
    # A bare object is neither JSON-native nor listable, so it still raises.
    c.provider = object()
    assert c.save_config() is False
    assert not list(tmp_path.glob("*.tmp"))


def test_save_config_never_raises(ffmod, tmp_path, monkeypatch):
    """It is called from the AI tab's Save button and from every generate."""
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path / "nope"))
    c = ffmod.AIChef.__new__(ffmod.AIChef)
    c.ollama_url = c.ollama_model = c.anthropic_key = c.anthropic_model = "x"
    c.provider = "ollama"
    assert c.save_config() is False


def test_the_config_holding_the_key_is_not_world_readable(ffmod, tmp_path, monkeypatch):
    """POSIX only — Windows has no mode bits and inherits the home ACL."""
    import os
    import sys
    if sys.platform == "win32":
        pytest.skip("no POSIX mode bits on Windows")
    monkeypatch.setattr(ffmod.os.path, "expanduser", lambda p: str(tmp_path))
    c = ffmod.AIChef()
    c.anthropic_key = "sk-ant-secret"
    c.save_config()
    mode = os.stat(tmp_path / ".flavorforge_config.json").st_mode
    assert not (mode & 0o077), f"mode {oct(mode & 0o777)} — key readable by others"
