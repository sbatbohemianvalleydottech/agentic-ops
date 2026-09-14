import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULTS = Path(__file__).parent / "rubric.toml"


@dataclass(frozen=True)
class Rubric:
    required_moments: tuple[str, ...]
    # Only blame when a person is the subject of the same sentence.
    blame_phrases: tuple[str, ...]
    export_window_days: int
    grade_scale: tuple[str, ...]
    min_contributing_factors: int
    # The two below default to empty so a rubric copied before they existed
    # still loads. Empty means the conditional phrases can never fire, which is
    # the safe direction: a check that goes quiet is better than one that cries
    # wolf on every "the job failed to start".
    blame_phrases_standalone: tuple[str, ...] = ()
    human_subjects: tuple[str, ...] = ()

    def __post_init__(self):
        if len(set(self.grade_scale)) < 2:
            raise ValueError(
                f"grade_scale needs at least two distinct grades, got "
                f"{self.grade_scale!r}; one grade makes disagreement impossible "
                "and the gate meaningless"
            )


def load_rubric(path: Path | None = None) -> Rubric:
    raw = tomllib.loads((path or DEFAULTS).read_text())

    return Rubric(
        required_moments=tuple(raw["required_moments"]),
        blame_phrases=tuple(raw["blame_phrases"]),
        # Optional, so a rubric copied before these existed still loads.
        blame_phrases_standalone=tuple(raw.get("blame_phrases_standalone", ())),
        human_subjects=tuple(raw.get("human_subjects", ())),
        export_window_days=int(raw["export_window_days"]),
        grade_scale=tuple(raw["grade_scale"]),
        min_contributing_factors=int(raw["min_contributing_factors"]),
    )
