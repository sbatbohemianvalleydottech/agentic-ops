"""setup/README.md is a document another Claude Code session executes, so it is checked
like code.

These run offline in both CI jobs. They cannot show that the steps reproduce the author's
configuration: setup/verify.sh does that, on a machine with Claude Code. What they catch is
the document breaking in the ways a reader's session would hit first. A block that does not
parse, steps out of order, a settings file that is not JSON, a step writing outside the
active config directory, a command that prints the key, or a secret pasted in.

The contract these rely on is specs/010-executable-setup/contracts/step-blocks.md.
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "setup" / "README.md"
SCANNED_FOR_SECRETS = (ROOT / "setup", ROOT / "specs" / "010-executable-setup")

FENCED_BASH = re.compile(r"^```bash[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
STEP_HEADER = re.compile(r"# step (\d+): \S")
HEREDOC_OPENER = re.compile(r"<<-?[ \t]*(['\"]?)[A-Za-z_]+\1")
SETTINGS_BODY = re.compile(r"settings\.json\" <<'EOF'\n(.*?)^EOF$", re.MULTILINE | re.DOTALL)

# Shapes only. The suite elsewhere carries fake keys on purpose to prove redaction, which is
# why this scans what feature 010 adds rather than the whole repository.
SECRET_SHAPES = {
    "Context7 key": re.compile(r"ctx7sk-[0-9A-Za-z-]{8,}"),
    "Anthropic key": re.compile(r"sk-ant-[0-9A-Za-z_-]{8,}"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "GitHub token": re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,}"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def executable_blocks() -> list[str]:
    blocks = FENCED_BASH.findall(README.read_text())
    return [block for block in blocks if block.startswith(("# step ", "# check"))]


def steps() -> list[str]:
    return [block for block in executable_blocks() if block.startswith("# step ")]


def first_line(block: str) -> str:
    return block.splitlines()[0]


def test_the_document_has_steps_and_exactly_one_check():
    assert README.is_file(), "setup/README.md does not exist"
    assert steps(), "no step blocks"
    checks = [block for block in executable_blocks() if block.startswith("# check")]
    assert len(checks) == 1


def test_steps_are_numbered_from_one_without_gaps():
    numbers = []
    for block in steps():
        header = STEP_HEADER.match(block)
        assert header, f"malformed step header: {first_line(block)!r}"
        numbers.append(int(header.group(1)))
    assert numbers == list(range(1, len(numbers) + 1))


def test_every_executable_block_parses_as_bash():
    for block in executable_blocks():
        result = subprocess.run(["bash", "-n"], input=block, capture_output=True, text=True)
        assert result.returncode == 0, f"{first_line(block)}: {result.stderr}"


def test_file_contents_are_never_expanded_by_the_shell():
    for block in steps():
        for quote in HEREDOC_OPENER.findall(block):
            assert quote == "'", f"unquoted heredoc in {first_line(block)!r}"


def test_the_settings_step_writes_valid_json():
    bodies = [m.group(1) for block in steps() if (m := SETTINGS_BODY.search(block))]
    assert len(bodies) == 1, "expected exactly one step writing settings.json"
    assert isinstance(json.loads(bodies[0]), dict)


def test_steps_write_only_under_the_active_config_directory():
    for block in steps():
        rest = block.replace("${CLAUDE_CONFIG_DIR:-$HOME/.claude}", "")
        assert "~/.claude" not in rest, first_line(block)
        assert "$HOME/.claude" not in rest, first_line(block)


def test_nothing_executable_prints_the_context7_key():
    for block in executable_blocks():
        assert "claude mcp get" not in block, first_line(block)
        for line in block.splitlines():
            if re.match(r"\s*(echo|printf|printenv)\b", line):
                assert "CONTEXT7_API_KEY" not in line, line


def test_nothing_feature_010_adds_holds_a_secret():
    scanned = []
    for root in SCANNED_FOR_SECRETS:
        files = [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []
        for path in files:
            text = path.read_text(errors="ignore")
            for kind, shape in SECRET_SHAPES.items():
                assert not shape.search(text), f"{kind} shape in {path.relative_to(ROOT)}"
            scanned.append(path)
    assert README in scanned, "the scan never read setup/README.md"
