"""The prompt version is computed from the prompts, not typed by hand.

It was `PROMPT_VERSION = "1"` with a comment asking whoever edits a prompt to
remember to bump it. Everywhere else this repository mechanises its own
distrust: an AST check enforces the import boundary, a contract test enforces
no network, a floor enforces coverage. This one spot asked a human to
remember, inside the mechanism built to tell a prompt regression from noise.

A stale version is worse than none. It does not merely lose the attribution,
it asserts that two different prompts were the same one.
"""

import pytest

# The adapter is an optional extra, and the core CI job installs no provider
# library. Skipping the module is right here: this is a fact about the adapter,
# unlike the exit contract or the ledger, which must hold with nothing installed.
pytest.importorskip("litellm")

from ensemble.providers.litellm import (  # noqa: E402
    _JUDGE_PROMPT,
    _RATER_PROMPT,
    PROMPT_VERSION,
    version_of,
)


def test_the_version_is_the_one_derived_from_the_shipped_prompts():
    assert PROMPT_VERSION == version_of(_RATER_PROMPT, _JUDGE_PROMPT)


def test_editing_the_rater_prompt_changes_it():
    assert version_of(_RATER_PROMPT + " ", _JUDGE_PROMPT) != PROMPT_VERSION


def test_editing_the_judge_prompt_changes_it():
    assert version_of(_RATER_PROMPT, _JUDGE_PROMPT + " ") != PROMPT_VERSION


def test_swapping_the_two_prompts_changes_it():
    """Order matters, so a rater prompt pasted into the judge slot is visible."""
    assert version_of(_JUDGE_PROMPT, _RATER_PROMPT) != PROMPT_VERSION


def test_the_same_text_always_gives_the_same_version():
    assert version_of("a", "b") == version_of("a", "b")


def test_it_is_short_enough_to_read_in_a_ledger_row():
    assert len(PROMPT_VERSION) <= 16
    assert PROMPT_VERSION.isalnum()


def test_it_is_not_a_hand_typed_counter():
    """Guards the whole point. A literal would pass every test above but one."""
    assert PROMPT_VERSION not in {"1", "2", "3", "v1", ""}
