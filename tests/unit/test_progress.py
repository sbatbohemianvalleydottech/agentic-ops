"""Progress during a run.

Silence and a hang are indistinguishable, and the reasonable response to an
apparent hang is to kill it, which wastes everything already paid for.
"""

from ensemble.progress import SilentProgress, StderrProgress


def test_one_line_is_emitted_per_completed_unit(capsys):
    progress = StderrProgress()

    progress.step("rater anthropic/claude-opus-5", 0.0058)
    progress.step("rater gemini/gemini-3.8-flash", 0.0002)

    lines = [line for line in capsys.readouterr().err.splitlines() if line.strip()]
    assert len(lines) == 2
    assert "anthropic/claude-opus-5" in lines[0]


def test_the_running_cost_accumulates(capsys):
    progress = StderrProgress()

    progress.step("one", 0.01)
    progress.step("two", 0.02)

    assert "0.03" in capsys.readouterr().err.splitlines()[-1]


def test_progress_goes_to_stderr_and_never_to_stdout(capsys):
    """So redirecting stdout to a file yields a clean report."""
    StderrProgress().step("anything", 0.001)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "anything" in captured.err


def test_progress_uses_no_terminal_control_codes(capsys):
    """It has to be readable in a CI log and a piped file, not just a TTY."""
    StderrProgress().step("anything", 0.001)

    assert "\x1b" not in capsys.readouterr().err


def test_the_silent_reporter_emits_nothing(capsys):
    """The deterministic path makes no model calls, so it has nothing to say."""
    progress = SilentProgress()

    progress.step("anything", 0.001)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
