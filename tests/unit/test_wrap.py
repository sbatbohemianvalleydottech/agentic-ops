"""Rendering model prose without altering it.

A wrapper that silently rewrote what a model said would be a quieter version
of the bug this feature fixes: the report showing something other than the
evidence it claims to be showing.
"""

from ensemble.explain import wrap


def test_long_reasoning_is_wrapped_rather_than_emitted_as_one_line():
    text = "word " * 80
    lines = wrap(text, indent=6, width=78)

    assert len(lines) > 1
    assert all(len(line) <= 78 for line in lines)


def test_every_line_carries_the_requested_indent():
    lines = wrap("word " * 40, indent=6, width=78)

    assert all(line.startswith(" " * 6) for line in lines)


def test_wrapping_does_not_alter_the_text_beyond_whitespace():
    """The point of showing reasoning is that a reviewer can check it. Text that
    has been rewritten on the way to the screen is not evidence."""
    text = (
        "The stated cause is \"a schema migration locked the orders table\". "
        "That is the trigger, not the cause: nothing here explains why a "
        "migration could take a table lock during business hours without a "
        "statement timeout. [rca-hollow:cause]"
    )

    assert " ".join("".join(wrap(text, indent=4, width=70)).split()) == " ".join(
        text.split()
    )


def test_newlines_in_model_output_cannot_break_the_layout():
    """One model's formatting choice must not reflow a report about it."""
    lines = wrap("first line\n\n\nsecond line\tthird", indent=4, width=78)

    assert all(line.startswith("    ") for line in lines)
    assert not any("\n" in line or "\t" in line for line in lines)


def test_empty_reasoning_is_rendered_as_explicitly_empty():
    """A model that graded without explaining is a fact about the run, not an
    absence to be tidied away."""
    lines = wrap("", indent=4, width=78)

    assert len(lines) == 1
    assert "no reasoning" in lines[0].lower()
