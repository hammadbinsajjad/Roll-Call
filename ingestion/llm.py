"""LLM integration layer via litellm — one API for any provider.

Configuration, from ingestion/.env or environment:
  - LLM_API_KEY    (required; falls back to OPENAI_API_KEY for backward compat)
  - LLM_MODEL      (provider-prefixed, e.g. "openrouter/google/gemma-3-27b-it"
                   for OpenRouter, "openai/gemma-3-27b-it" + LLM_BASE_URL for a
                   local server; defaults to the placeholder below)
  - LLM_BASE_URL   (api base for self-hosted/OpenAI-compatible endpoints)

LLM-side only: ingestion.py provides the team members and both
ingestions' data, and handles storage of this layer's returned results.
"""

import json
import os

import litellm
import sentry_sdk

MODEL = "unsloth/gemma-4-E4B-it-qat-GGUF:Q4_K_XL"  # litellm routes bare names to OpenAI by default

SYSTEM_PROMPT = (
    "You are Roll-Call's reporting assistant. For one team member you "
    "receive, for a single day: their GitHub pull requests and commits "
    "('touched_today': true), ongoing open pull requests and Linear issues "
    "assigned to them that simply haven't been updated today ('touched_today': "
    "false) — include those as ongoing work — plus direct pushes to branches "
    "without a pull request (the 'pushes' list). "
    "Cross-links are precomputed: a linear issue is related to a PR when "
    "the issue name appears as a whole or as a substring in the PR title "
    "or branch name (case-insensitive); each PR lists the identifiers of "
    "issue(s) it relates to in 'related_issues', and each issue lists the "
    "PR numbers it relates to in 'related_pull_requests'. "
    "Write a clear, human-readable daily work summary for this member in "
    "plain English: what they worked on, connecting each issue to the "
    "PRs, branch and commits that implement it. Only state what the data "
    "shows; do not invent activity."
)


class LLMError(RuntimeError):
    pass


def _llm_config():
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise LLMError(
            "LLM_API_KEY is not set (ingestion/.env or environment). "
            "OPENAI_API_KEY is also accepted."
        )
    model = os.getenv("LLM_MODEL") or MODEL
    api_base = os.getenv("LLM_BASE_URL") or None
    if api_base:
        # OpenAI-compatible endpoint (local Gemma server etc.): litellm needs
        # an explicit provider; add "openai/" unless one is present already.
        try:
            litellm.get_llm_provider(model=model)
        except Exception:
            model = f"openai/{model}"
    return {"model": model, "api_key": api_key, "api_base": api_base}


def build_member_report(member, payload):
    """Send one member's combined payload to the LLM; returns the summary."""
    # gen_ai.invoke_agent wraps one report run; the LiteLLM integration's
    # gen_ai.chat span (litellm.completion) nests under it. Sentry is a no-op
    # unless ingestion.main ran sentry_sdk.init with a SENTRY_DSN.
    with sentry_sdk.start_span(
        op="gen_ai.invoke_agent", name="invoke_agent Report Writer"
    ) as span:
        # shortcut: docs show an attributes= kwarg; it lands after 2.72.0, so
        # set_data until the SDK catches up. Set before the call (span start).
        span.set_data("gen_ai.operation.name", "invoke_agent")
        span.set_data("gen_ai.agent.name", "Report Writer")
        span.set_data("gen_ai.system_instructions", SYSTEM_PROMPT)
        span.set_data("gen_ai.input.messages", json.dumps([
            {"role": "user", "parts": [{"type": "text", "content": json.dumps(payload)}]},
        ]))
        try:
            resp = litellm.completion(
                **_llm_config(),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
            summary = resp.choices[0].message.content
        except Exception as exc:
            span.set_status("internal_error")
            span.set_data("error.type", type(exc).__name__)
            raise LLMError(f"LLM API call failed for {member.get('member_name')}: {exc}") from exc
        span.set_data("gen_ai.output.messages", json.dumps([
            {"role": "assistant", "parts": [{"type": "text", "content": str(summary)}]},
        ]))
    return summary  # storage happens once, in build_report's loop


def member_payload(member, github_activity, linear_activity):
    """Assemble one member's combined LLM input from both ingestions."""
    issues = issues_for_member(member, linear_activity)
    prs, issues = link_issues_to_prs(prs_for_member(member, github_activity), issues)
    entry = _activity_entry(github_activity, member.get("github_username"))
    pushes = []
    for repo_name, repo_data in (entry.get("repos") or {}).items():
        pushes.extend({"repo": repo_name, **c} for c in repo_data.get("pushes", []))
    return {
        "member_name": member.get("member_name"),
        "github_username": member.get("github_username"),
        "linear_email": member.get("linear_email"),
        "pull_requests": prs,
        "pushes": pushes,
        "issues": issues,
    }


def prs_for_member(member, github_activity):
    """The member's PRs from today's GitHub ingestion, keyed by username."""
    entry = _activity_entry(github_activity, member.get("github_username"))
    return [
        pr
        for repo_data in (entry.get("repos") or {}).values()
        for pr in repo_data["pull_requests"]
    ]


def issues_for_member(member, linear_activity):
    """The member's issues from today's Linear ingestion, keyed by email."""
    entry = _activity_entry(linear_activity, member.get("linear_email"))
    return [
        issue
        for team_data in (entry.get("teams") or {}).values()
        for issue in team_data["issues"]
    ]


def link_issues_to_prs(prs, issues):
    """Pair issues with PRs by issue identifier (e.g. ROLL-5) or issue name
    appearing in the PR title or branch name, case-insensitive, whole or
    substring; annotate both sides."""
    prs_out = [{**p, "related_issues": []} for p in prs]
    issues_out = [{**i, "related_pull_requests": []} for i in issues]
    for issue, issue_out in zip(issues, issues_out):
        name = (issue.get("title") or "").lower()
        identifier = (issue.get("identifier") or "").lower()
        for pr, pr_out in zip(prs, prs_out):
            hay = f"{(pr.get('title') or '')} {(pr.get('branch') or '')}".lower()
            if (identifier and identifier in hay) or (name and name in hay):
                issue_out["related_pull_requests"].append(pr["number"])
                pr_out["related_issues"].append(issue["identifier"])
    return prs_out, issues_out


def _activity_entry(activity, identifier):
    """One user's entry from either ingestion, case-insensitive by key."""
    return activity.get((identifier or "").lower(), {})


def build_reports(members, github_activity: dict, linear_activity: dict) -> list:
    """One LLM call per team member. Returns one dict per member:

        {"member": <member>, "input_data": <payload>, "summary": <str>}

    Members with no recorded work get a fixed summary and skip the
    (paid) LLM call, but their day is still returned for storage.
    """
    results = []
    for member in members:
        payload = member_payload(member, github_activity, linear_activity)
        if not payload["pull_requests"] and not payload["issues"] and not payload["pushes"]:
            summary = "No activity recorded today."
        else:
            summary = build_member_report(member, payload)
        results.append({"member": member, "input_data": payload, "summary": summary})
    return results
