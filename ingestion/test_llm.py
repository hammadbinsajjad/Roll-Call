"""Offline asserts for the member matching / issue-PR linking in llm.py.

Mostly no network: only the live-LLM block at the bottom calls the model,
and it skips itself when OPENAI_API_KEY isn't configured.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
from llm import build_reports, issues_for_member, link_issues_to_prs, prs_for_member

github_activity = {
    "devuser": {
        "username": "devuser",
        "repos": {
            "owner/repo": {
                "pull_requests": [
                    {"number": 1, "title": "ROLL-5 ingestion", "branch": "feature/roll-5-implementation"},
                    {"number": 2, "title": "unrelated cleanup", "branch": "misc/cleanup"},
                ]
            }
        },
    }
}

linear_activity = {
    "dev@x.com": {
        "username": "dev@x.com",
        "teams": {
            "Team": {
                "issues": [
                    {"identifier": "ROLL-5", "title": "Ingestion of Linear issues and Github PRs"},
                    {"identifier": "ROLL-9", "title": "Something else entirely"},
                ]
            }
        },
    }
}

member = {"github_username": "DevUser", "linear_email": "DEV@x.com", "member_name": "Dev"}

assert len(prs_for_member(member, github_activity)) == 2      # case-insensitive username
assert len(issues_for_member(member, linear_activity)) == 2   # case-insensitive email

prs, issues = link_issues_to_prs(prs_for_member(member, github_activity), issues_for_member(member, linear_activity))
assert prs[0]["related_issues"] == ["ROLL-5"]      # title contains issue name
assert prs[1]["related_issues"] == []
assert issues[0]["related_pull_requests"] == [1]   # branch contains issue name
assert issues[1]["related_pull_requests"] == []
assert issues[0]["identifier"] == "ROLL-5" and prs[0]["number"] == 1  # originals untouched

reported = prs_for_member({"github_username": "nobody", "linear_email": "x"},
                          github_activity)
assert reported == []

assert db.get_repos() == ["hammadbinsajjad/Roll-Call"]          # placeholder values (file-backed)
assert db.get_team_members() == [{
    "github_username": "hammadbinsajjad",
    "linear_email": "supperhammad2002@gmail.com",
    "member_name": "Hammad Bin Sajjad",
}]

# build_reports with no members returns nothing; with no data, skips the LLM
assert build_reports([], {}, {}) == []
empty = build_reports([member], {}, {})
assert empty == [{"member": member, "input_data": {
    "member_name": "Dev", "github_username": "DevUser", "linear_email": "DEV@x.com",
    "pull_requests": [], "pushes": [], "issues": []}, "summary": "No activity recorded today."}], empty

# sentry agent-tracing wiring (offline): build_reports must wrap each LLM run in
# a gen_ai.invoke_agent span with JSON-stringified messages. A recorder stands
# in for sentry_sdk.start_span; the LiteLLM integration's chat span is only
# exercised by a live SENTRY_DSN run (see temp/sentry-agent-tracing-plan.md §3).
import json as _json
import llm as _llm
from types import SimpleNamespace as _NS


class _RecSpan:
    def __init__(self, op, name, attributes):
        self.op, self.name, self.attributes = op, name, attributes or {}
        self.data, self.status = {}, None
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def set_data(self, key, value): self.data[key] = value
    def set_status(self, value): self.status = value


class _Recorder:
    def __init__(self): self.spans = []
    def __call__(self, op=None, name=None, attributes=None, **kw):
        span = _RecSpan(op, name, attributes)
        self.spans.append(span)
        return span


os.environ["LLM_API_KEY"] = "test"
_real_start_span, _real_completion = _llm.sentry_sdk.start_span, _llm.litellm.completion
_rec = _Recorder()
_llm.sentry_sdk.start_span, _llm.litellm.completion = _rec, (
    lambda **kw: _NS(choices=[_NS(message=_NS(content="a summary"))])
)
try:
    _result = build_reports([member], github_activity, linear_activity)[0]
    assert _result["summary"] == "a summary", _result["summary"]
    _span = _rec.spans[0]
    assert _span.op == "gen_ai.invoke_agent" and _span.name == "invoke_agent Report Writer", _span.op
    assert _span.data["gen_ai.operation.name"] == "invoke_agent"
    assert _span.data["gen_ai.agent.name"] == "Report Writer"
    _msgs = _json.loads(_span.data["gen_ai.input.messages"])
    assert _msgs[0]["role"] == "user" and "DevUser" in _msgs[0]["parts"][0]["content"]
    _out = _json.loads(_span.data["gen_ai.output.messages"])
    assert _out[0]["parts"][0]["content"] == "a summary", _out
    # failure path: the span must be marked for Sentry's error widgets
    def _boom(**kw): raise ValueError("model down")
    _llm.litellm.completion = _boom
    try:
        _llm.build_member_report(member, {})
        raise AssertionError("expected LLMError")
    except _llm.LLMError:
        assert _rec.spans[-1].status == "internal_error", _rec.spans[-1].status
        assert _rec.spans[-1].data["error.type"] == "ValueError", _rec.spans[-1].data
finally:
    _llm.sentry_sdk.start_span, _llm.litellm.completion = _real_start_span, _real_completion
    del os.environ["LLM_API_KEY"]

# live test: skipped when OPENAI_API_KEY is absent from the env or ingestion/.env
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

if not os.getenv("OPENAI_API_KEY"):
    print("skipped the live LLM assert (OPENAI_API_KEY not set)")
else:
    results = build_reports([member], github_activity, linear_activity)
    result = results[0]
    # the plumbing is deterministic; the model's wording is not, so only assert that
    assert result["input_data"]["pull_requests"][0]["related_issues"] == ["ROLL-5"]
    assert isinstance(result["summary"], str) and result["summary"].strip(), result["summary"]
    print("live LLM assert passed; sample summary:", result["summary"][:120].replace("\n", " "))

print("all asserts passed")
