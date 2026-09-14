"""LiteLLM-backed provider.

LiteLLM is the seam because it is what the model gateway this targets already
runs, so the artifact speaks the platform's interface rather than sitting beside
it. Importing this module requires litellm installed; importing `ensemble` does
not. Install with `pip install -e ".[providers]"`.

Model strings are LiteLLM's provider-prefixed form, for example
`anthropic/claude-opus-5` or `gemini/gemini-3.8-flash`. Nothing here hardcodes a
model, so changing provider is configuration.
"""

import json
import os

import litellm
from litellm import completion, supports_response_schema

from ..types import EvidenceBundle, JudgeVerdict, RaterVerdict, Rubric
from . import Call, Usage, call_cost, redact

# The vendor prints a banner and a support link on every error. Suppressed so a
# halt report is legible. The error itself is not suppressed; it is carried
# deliberately on the Call instead of being shouted at stderr.
litellm.suppress_debug_info = True

# Schemas rather than a bare json_object. LiteLLM passes these natively where the
# provider supports them and falls back to a tool call where it does not, so the
# reply is schema-valid instead of merely valid JSON. That matters here: a rater
# returning a well-formed object with no `grade` key would otherwise surface as a
# missing verdict and halt a decision for the wrong reason.
RATER_SCHEMA = {
    "type": "object",
    "properties": {"grade": {"type": "string"}, "reasoning": {"type": "string"}},
    "required": ["grade", "reasoning"],
    "additionalProperties": False,
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"justified": {"type": "boolean"}, "reasoning": {"type": "string"}},
    "required": ["justified", "reasoning"],
    "additionalProperties": False,
}

# Evidence first, criteria last. The evidence is identical across every
# dimension and every rater; the criteria change per dimension. Stable content
# has to physically precede volatile content for a cache breakpoint to have a
# prefix to sit on. No cache_control is set yet, because at 308 evidence tokens
# we are below the 512-token minimum on Opus 5 and a marker would silently do
# nothing. See the preflight module.
_RATER_PROMPT = """EVIDENCE about {subject}:
{evidence}

You are grading the evidence above against a fixed rubric.

RUBRIC: {criteria}
PERMITTED GRADES: {scale}

Assign exactly one grade from the permitted list. Every part of your reasoning
must cite one of the evidence references above. If the evidence does not support
a claim, leave the claim out.

Reply with JSON only: {{"grade": "...", "reasoning": "..."}}"""

_JUDGE_PROMPT = """EVIDENCE about {subject}:
{evidence}

You are assessing whether a proposed grade is justified.

RUBRIC: {criteria}
PERMITTED GRADES: {scale}
PROPOSED GRADE: {grade}

Does this evidence support this grade under this rubric? Judge the grade on its
merits. Do not assume it is correct because it was proposed.

Reply with JSON only: {{"justified": true or false, "reasoning": "..."}}"""


def _render(evidence: EvidenceBundle) -> str:
    return "\n".join(
        f"- [{record.ref}] {record.source} {record.timestamp:%Y-%m-%d}: {record.content}"
        for record in evidence.records
    )


def _response_format(model: str, schema: dict, name: str) -> dict:
    try:
        supported = supports_response_schema(model=model)
    except Exception:
        # An unrecognised model is not a reason to fail the call. Fall back to
        # plain JSON and let the request itself decide whether the model exists.
        supported = False

    if supported:
        return {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        }
    return {"type": "json_object"}


def _extra_headers(model: str) -> dict | None:
    """An org-scoped Anthropic key needs a workspace on every request. Supplying
    it here means an existing key works without being recreated."""
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace and model.startswith("anthropic/"):
        return {"anthropic-workspace-id": workspace}
    return None


def _priced(response) -> Usage:
    """Usage for a call that already succeeded.

    Deliberately outside the request's error handling. Cost is bookkeeping, and
    a model that answered correctly but has no published price must not have its
    verdict discarded over it. That is fabrication in the opposite direction:
    the system looking broken while working.
    """
    return Usage(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
        cost=call_cost(response),
    )


def _call(
    model: str, prompt: str, schema: dict, name: str
) -> tuple[dict | None, Usage, str | None]:
    """One model call. A failure returns no payload and says why."""
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": _response_format(model, schema, name),
    }
    headers = _extra_headers(model)
    if headers:
        kwargs["extra_headers"] = headers

    try:
        response = completion(**kwargs)
        payload = json.loads(response.choices[0].message.content)
    except Exception as error:
        # Deliberately broad. A provider outage, a rate limit, a dead model, an
        # unfunded account and a malformed reply all mean the same thing here:
        # there is no verdict. What changed after the first live run is that the
        # reason travels with the absence instead of being thrown away.
        return None, Usage(), redact(f"{type(error).__name__}: {' '.join(str(error).split())}")

    return payload, _priced(response), None


class LiteLLMProvider:
    def grade(self, rubric: Rubric, evidence: EvidenceBundle, model: str) -> Call:
        payload, usage, error = _call(
            model,
            _RATER_PROMPT.format(
                criteria=rubric.criteria,
                scale=", ".join(rubric.scale),
                subject=evidence.subject,
                evidence=_render(evidence),
            ),
            RATER_SCHEMA,
            "rater_verdict",
        )
        if payload is None:
            return Call(verdict=None, usage=usage, error=error)
        if "grade" not in payload:
            return Call(
                verdict=None,
                usage=usage,
                error=f"reply had no 'grade' key: {sorted(payload)}",
            )

        # The grade is passed through unchecked. Validating it against the scale
        # is the gate's job, and coercing it here would hide a broken prompt.
        return Call(
            verdict=RaterVerdict(
                rater=model,
                grade=str(payload["grade"]),
                reasoning=str(payload.get("reasoning", "")),
            ),
            usage=usage,
        )

    def judge(
        self, rubric: Rubric, evidence: EvidenceBundle, grade: str, model: str
    ) -> Call:
        payload, usage, error = _call(
            model,
            _JUDGE_PROMPT.format(
                criteria=rubric.criteria,
                scale=", ".join(rubric.scale),
                grade=grade,
                subject=evidence.subject,
                evidence=_render(evidence),
            ),
            JUDGE_SCHEMA,
            "judge_verdict",
        )
        if payload is None:
            return Call(verdict=None, usage=usage, error=error)
        if "justified" not in payload:
            return Call(
                verdict=None,
                usage=usage,
                error=f"reply had no 'justified' key: {sorted(payload)}",
            )

        return Call(
            verdict=JudgeVerdict(
                justified=bool(payload["justified"]),
                reasoning=str(payload.get("reasoning", "")),
            ),
            usage=usage,
        )
