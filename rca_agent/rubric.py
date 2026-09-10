import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULTS = Path(__file__).parent / "rubric.toml"


@dataclass(frozen=True)
class Rubric:
    required_moments: tuple[str, ...]
    blame_phrases: tuple[str, ...]
    export_window_days: int
    grade_scale: tuple[str, ...]
    min_contributing_factors: int

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
        export_window_days=int(raw["export_window_days"]),
        grade_scale=tuple(raw["grade_scale"]),
        min_contributing_factors=int(raw["min_contributing_factors"]),
    )
