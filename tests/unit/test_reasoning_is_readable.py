"""A verdict's reasoning reaches a human as characters, not as escape sequences.

Models double-escape non-ASCII when they quote source text: asked to assess a
document containing "the service's authentication permissions" with a
typographic apostrophe, the reply comes back carrying the literal six
characters \\u2019 rather than the character they encode. Our parser decodes
the reply's JSON correctly; the model had escaped the backslash as well, so
what survives is a sequence no reader wants.

This was visible once as a stray em dash and dismissed as cosmetic. Running the
tool over published incident reports showed what it actually is: every real
document has typographic punctuation, so every real report was going to carry
these. The report is the whole of what a human gets when a judgement halts, and
handing them \\u2019 is a display fault.

Decoding an escape is not editing what the assessor said. \\u2019 and the
character are the same character, one written as an encoding of the other. What
would be editing is changing a word, and nothing here does that.
"""

import pytest

from ensemble.providers import readable

UNCHANGED = [
    "Plain ASCII reasoning with nothing to decode.",
    "A real apostrophe's fine, and so is an em dash \u2014 like this.",
    r"A Windows path C:\Users\someone stays as it is.",
    r"A single backslash \ on its own.",
    r"An incomplete escape \u201 is left alone.",
    r"A malformed one \uZZZZ is left alone.",
    "",
]


@pytest.mark.parametrize("text", UNCHANGED)
def test_text_with_nothing_to_decode_is_returned_unchanged(text):
    assert readable(text) == text


def test_an_escaped_apostrophe_becomes_the_character():
    assert readable(r"the service\u2019s permissions") == "the service\u2019s permissions"


def test_an_escaped_em_dash_becomes_the_character():
    assert readable(r"states \u2014 investigation at 20:39") == (
        "states \u2014 investigation at 20:39"
    )


def test_several_in_one_string_are_all_decoded():
    decoded = readable(r"\u2018quoted\u2019 and \u2014 dashed")
    assert decoded == "\u2018quoted\u2019 and \u2014 dashed"


def test_decoding_is_idempotent():
    once = readable(r"the service\u2019s permissions")
    assert readable(once) == once


def test_a_real_backslash_before_a_decoded_escape_survives():
    r"""C:\path\u2019 is a path, not an escape. Rare, and it must not corrupt."""
    assert "\\" in readable(r"C:\path\u2019end")


def test_the_verdict_carries_readable_reasoning(monkeypatch):
    """The whole point: it has to reach the report decoded."""
    pytest.importorskip("litellm")
    import ensemble.providers.litellm as adapter
    from tests.unit.test_providers import _Response

    class Escaped(_Response):
        def __init__(self):
            super().__init__()
            import json

            payload = {"grade": "strong", "reasoning": r"the service\u2019s permissions"}
            self.choices[0].message.content = json.dumps(payload)

    monkeypatch.setattr(adapter, "completion", lambda **kwargs: Escaped())
    monkeypatch.setattr(adapter, "supports_response_schema", lambda **kwargs: True)
    monkeypatch.setattr("ensemble.providers._recompute", lambda response: 0.001)

    from ensemble.types import EvidenceBundle, EvidenceRecord, Rubric

    call = adapter.LiteLLMProvider().grade(
        Rubric(name="r", criteria="c", scale=("weak", "strong")),
        EvidenceBundle(
            subject="s",
            records=(
                EvidenceRecord(
                    source="src",
                    timestamp=__import__("datetime").datetime(2026, 1, 1),
                    ref="ref",
                    content="content",
                ),
            ),
        ),
        "some/model",
    )

    assert "\\u2019" not in call.verdict.reasoning
    assert "\u2019" in call.verdict.reasoning
