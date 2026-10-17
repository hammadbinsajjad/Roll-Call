"""LLM integration layer.

Deliberately SDK-agnostic: once you pick a provider (OpenAI SDK,
google-genai, etc.), replace the body of build_report() with the real
API call and add any config (base URL, model name, key from env).
"""

SYSTEM_PROMPT = (
    "You are Roll-Call's reporting assistant. You receive raw developer "
    "activity collected from GitHub (and possibly other sources) and turn "
    "it into a clear human-readable daily report per developer."
)


def build_report(github_activity: dict, other_activity: dict | None) -> str:
    """Send both ingestions to the LLM and return the human-readable report.

    Expected input shape:
      github_activity: {"<user>": {"username": ..., "repos": {"<owner/repo>": {"pull_requests": [...]}}}}
      other_activity:  same kind of nested mapping from the second source, or None
    """
    # TODO: implement once an LLM SDK is chosen. Sketch (OpenAI-style):
    #   client = OpenAI()  # reads OPENAI_API_KEY from env
    #   resp = client.chat.completions.create(
    #       model="gpt-4o-mini",
    #       messages=[
    #           {"role": "system", "content": SYSTEM_PROMPT},
    #           {"role": "user", "content": json.dumps({
    #               "github": github_activity,
    #               "other": other_activity,
    #           })},
    #       ],
    #   )
    #   return resp.choices[0].message.content
    raise NotImplementedError("pick an LLM SDK and implement build_report()")
