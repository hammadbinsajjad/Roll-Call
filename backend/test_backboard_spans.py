"""Offline assert for the Sentry gen_ai.chat span around Backboard calls.

Patches app.services.backboard._headerless_post so no network is needed; a
recorder stands in for sentry_sdk.start_span. Run from anywhere:
    python test_backboard_spans.py
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("BACKBOARD_API_KEY", "test")        # only presences are checked
os.environ.setdefault("BACKBOARD_ASSISTANT_ID", "test")

import sentry_sdk  # the real module; only start_span is swapped out below

from app.services import backboard


class _RecSpan:
    def __init__(self, op, name, attributes):
        self.op, self.name, self.attributes = op, name, attributes or {}
        self.data, self.status = {}, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def set_data(self, key, value):
        self.data[key] = value

    def set_status(self, value):
        self.status = value


class _Recorder:
    def __init__(self):
        self.spans = []

    def __call__(self, op=None, name=None, attributes=None, **kw):
        span = _RecSpan(op, name, attributes)
        self.spans.append(span)
        return span


_real_start_span = sentry_sdk.start_span
_rec = _Recorder()
sentry_sdk.start_span = _rec

_calls = {"path": None, "body": None}


def _fake_post(path, json_body=None, timeout=60.0):
    _calls["path"], _calls["body"] = path, json_body
    return SimpleNamespace(
        status_code=200,
        content=b'{"reply":"hi","thread_id":"t1"}',
        json=lambda: {"reply": "hi", "thread_id": "t1"},
    )


_real_post = backboard._headerless_post
backboard._headerless_post = _fake_post
try:
    reply, thread_id = backboard.send_message("what did Dev do?", thread_id="t1")
    assert (reply, thread_id) == ("hi", "t1"), (reply, thread_id)

    span = _rec.spans[0]
    assert span.op == "gen_ai.chat", span.op
    assert span.name == "chat google/gemma-4-26b-a4b-it", span.name
    assert span.data["gen_ai.operation.name"] == "chat"
    assert span.data["gen_ai.provider.name"] == "backboard"
    assert span.data["gen_ai.agent.name"] == "Backboard Chat"
    msgs = json.loads(span.data["gen_ai.input.messages"])
    assert msgs[0]["role"] == "user" and msgs[0]["parts"][0]["content"] == "what did Dev do?"
    out = json.loads(span.data["gen_ai.output.messages"])
    assert out[0]["role"] == "assistant" and out[0]["parts"][0]["content"] == "hi"
    assert _calls["path"] == "/threads/messages" and _calls["body"]["thread_id"] == "t1"

    # failure path: the span must be marked for Sentry's error widgets
    def _fail(path, json_body=None, timeout=60.0):
        return SimpleNamespace(status_code=503, content=b"")

    backboard._headerless_post = _fail
    try:
        backboard.send_message("again?")
        raise AssertionError("expected BackboardError")
    except backboard.BackboardError:
        err = _rec.spans[-1]
        assert err.status == "internal_error", err.status
        assert err.data["error.type"] == "HTTP503", err.data
finally:
    backboard._headerless_post = _real_post
    sentry_sdk.start_span = _real_start_span

print("all asserts passed")
