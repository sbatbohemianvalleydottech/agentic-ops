"""The exit-code contract every runnable thing here shares.

Before this, rca_agent found five defective reviews and exited 0, so it could
report a problem and pass the build in the same breath. A tool that always
exits 0 cannot gate anything.
"""

import pytest

from ci import Exit, describe


def test_the_three_codes_are_what_a_shell_expects():
    assert (Exit.OK, Exit.BLOCKED, Exit.UNJUDGED) == (0, 1, 2)


def test_a_code_is_an_int_so_sys_exit_takes_it_directly():
    assert isinstance(Exit.BLOCKED, int)
    assert Exit.BLOCKED == 1


@pytest.mark.parametrize(
    "code,fragment",
    [(0, "nothing to stop for"), (1, "the answer is stop"), (2, "never means clean")],
)
def test_every_code_describes_itself_for_a_pipeline_log(code, fragment):
    assert fragment in describe(code)


def test_an_unknown_code_says_so_rather_than_guessing():
    assert "not part of this contract" in describe(9)


def test_unjudged_is_distinct_from_blocked():
    """A broken gate and a failed gate need different responses from a human.

    Collapsing them teaches people to ignore both.
    """
    assert Exit.UNJUDGED != Exit.BLOCKED


@pytest.mark.parametrize("module", ["plan_cost.cli", "rca_agent.cli", "cost_agent.cli"])
def test_every_cli_uses_the_shared_contract(module):
    """Not three opinions about what 2 means."""
    import importlib

    source = importlib.import_module(module).__file__
    with open(source) as handle:
        text = handle.read()

    assert "from ci import" in text, f"{module} does not use the shared exit contract"
