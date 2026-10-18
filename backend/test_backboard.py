"""Regression tests for the messed-up chat reply bug (run: python3 test_backboard.py)."""
from app.services import backboard


def test_strip_thought():
    assert backboard._strip_thought("thought\nReal answer") == "Real answer"
    assert backboard._strip_thought("THOUGHT\n\nReal answer") == "Real answer"
    assert backboard._strip_thought("thoughts about X\nanswer") == "thoughts about X\nanswer"
    assert backboard._strip_thought("normal reply") == "normal reply"


def test_get_thread_messages_filters_tool_and_thought():
    # shapes captured live from GET /threads/{id} on 2026-10-19
    thread = {"messages": [
        {"role": "user", "content": "can you get me details for hammadbinsajjad?", "created_at": "1"},
        {"role": "tool", "content": '[{"github_username": "hammadbinsajjad"}]', "created_at": "2"},
        {"role": "assistant", "content": "thought\nOn October 18, 2026, Hammad ...", "created_at": "3"},
        {"role": "assistant", "content": None, "created_at": "4"},  # tool-call turn, no text
    ]}
    # bypass HTTP: inline the same mapping via a monkeypatched _get
    orig_get = backboard._get
    fake = type("R", (), {"status_code": 200, "json": lambda s: thread, "content": b"x"})
    backboard._get = lambda path: fake()
    try:
        out = backboard.get_thread_messages("tid")
    finally:
        backboard._get = orig_get
    assert out == [
        {"role": "user", "content": "can you get me details for hammadbinsajjad?", "created_at": "1"},
        {"role": "assistant", "content": "On October 18, 2026, Hammad ...", "created_at": "3"},
    ], out


if __name__ == "__main__":
    test_strip_thought()
    test_get_thread_messages_filters_tool_and_thought()
    print("ok")
