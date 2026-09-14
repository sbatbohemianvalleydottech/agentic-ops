"""The free path exits 0 on both estates, with and without the saturation note.

Rendering must not move an exit code. Every plan fixture already has its code
pinned somewhere in this directory, and estate_a's paid path is pinned in
test_paid_paths_end_to_end, so this closes the one gap: the free path, on the
two estates that take different branches of the new note. estate_a has nothing
healthy and gets the note. estate_b has three healthy resources and does not.

Nothing here asserts the note's content. That is tested where it is rendered.
This asserts only that whichever branch runs, the answer to "did it work" is
the same one it was before the branch existed.
"""

from pathlib import Path

import pytest

from ci import Exit
from cost_agent.cli import main

FIXTURES = Path(__file__).resolve().parents[2] / "cost_agent" / "fixtures"


@pytest.mark.parametrize("estate,saturated", [("estate_a", True), ("estate_b", False)])
def test_the_free_path_exits_ok(capsys, estate, saturated):
    code = main([
        "--costs", str(FIXTURES / estate / "costs.csv"),
        "--inventory", str(FIXTURES / estate / "inventory.json"),
        "--as-of", "2026-09-01",
    ])
    out = capsys.readouterr().out

    assert code == Exit.OK
    # Guards the fixtures: if these stop differing, the parametrisation stops
    # testing two branches and quietly tests one twice.
    assert ("assessed resources" in out) is saturated
