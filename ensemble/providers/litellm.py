"""LiteLLM-backed provider.

LiteLLM is the seam because it is what the model gateway this work targets already
runs, so the artifact speaks the platform's interface rather than sitting beside
it. Importing this module requires litellm installed; importing `ensemble` does
not. Install with `pip install -e ".[providers]"`.

Model strings are LiteLLM's provider-prefixed form, for example
`anthropic/claude-opus-5` or `gemini/gemini-2.5-pro`. Nothing here hardcodes a
model, so changing provider is configuration.
"""

import json

from litellm import completion, completion_cost, supports_response_schema

from ..types import EvidenceBundle, JudgeVerdict, RaterVerdict, Rubric
from . import Usage

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

_RATER_PROMPT = """You are grading against a fixed rubric.

RUBRIC: {criteria}
PERMITTED GRADES: {scale}

EVIDENCE about {subject}:
{evidence}

Assign exactly one grade from the permitted list. Every part of your reasoning
must cite one of the evidence references above. If the evidence does not support
a claim, leave the claim out.

Reply with JSON only: {{"grade": "...", "reasoning": "..."}}"""

_JUDGE_PROMPT = """You are assessing whether a proposed grade is justified.

RUBRIC: {criteria}
PERMITTED GRADES: {scale}
PROPOSED GRADE: {grade}

EVIDENCE about {subject}:
{evidence}

Does this evidence support this grade under this rubric? Judge the grade on its
merits. Do not assume it is correct because it was proposed.

Reply with JSON only: {{"justified": true or false, "reasoning": "..."}}"""


def _render(evidence: EvidenceBundle) -> str:
    return "\n".join(
        f"- [{record.ref}] {record.source} {record.timestamp:%Y-%m-%d}: {record.content}"
        for record in evidence.records
    )


def _response_format(model: str, schema: dict, name: str) -> dict:
    if supports_response_schema(model=model):
        return {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True},
        }
    return {"type": "json_object"}


def _cost(response) -> float:
    """LiteLLM already prices every call and stashes the result on the response.

    Preferring that over recomputing with `completion_cost` avoids a second pass
    over the model tables and, more usefully, picks up a cost the provider
    reported itself, which the recomputation would replace with an estimate.
    """
    hidden = getattr(response, "_hidden_params", None) or {}
    reported = hidden.get("response_cost")
    if reported is not None:
        return float(reported)
    return float(completion_cost(completion_response=response))


def _call(model: str, prompt: str, schema: dict, name: str) -> tuple[dict | None, Usage]:
    """One model call. Any failure returns no payload rather than a default."""
    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=_response_format(model, schema, name),
        )
        payload = json.loads(response.choices[0].message.content)
        usage = Usage(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            cost=_cost(response),
        )
        return payload, usage
    except Exception:
        # Deliberately broad. A provider outage, a rate limit, a malformed
        # response and a JSON parse failure all mean the same thing here: there
        # is no verdict. Inventing one would be the failure this repo exists to
        # prevent, so the absence is passed up and the gate halts.
        return None, Usage()


class LiteLLMProvider:
    def grade(
        self, rubric: Rubric, evidence: EvidenceBundle, model: str
    ) -> tuple[RaterVerdict | None, Usage]:
        payload, usage = _call(
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
        if payload is None or "grade" not in payload:
            return None, usage

        # The grade is passed through unchecked. Validating it against the scale
        # is the gate's job, and coercing it here would hide a broken prompt.
        return (
            RaterVerdict(
                rater=model,
                grade=str(payload["grade"]),
                reasoning=str(payload.get("reasoning", "")),
            ),
            usage,
        )

    def judge(
        self, rubric: Rubric, evidence: EvidenceBundle, grade: str, model: str
    ) -> tuple[JudgeVerdict | None, Usage]:
        payload, usage = _call(
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
        if payload is None or "justified" not in payload:
            return None, usage

        return (
            JudgeVerdict(
                justified=bool(payload["justified"]),
                reasoning=str(payload.get("reasoning", "")),
            ),
            usage,
        )
