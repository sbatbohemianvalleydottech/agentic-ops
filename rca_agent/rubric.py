import tomllib
from dataclasses import dataclass
from pathlib import Path

from .types import RCA

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
    # A document recording none of these is not worth paying to grade. Empty
    # means the bar never fires, which is what a rubric copied before this
    # existed gets: the old behaviour.
    judgement_requires_any: tuple[str, ...] = ()

    def __post_init__(self):
        if len(set(self.grade_scale)) < 2:
            raise ValueError(
                f"grade_scale needs at least two distinct grades, got "
                f"{self.grade_scale!r}; one grade makes disagreement impossible "
                "and the gate meaningless"
            )
        unknown = [
            field
            for field in self.judgement_requires_any
            if field not in RCA.__dataclass_fields__
        ]
        if unknown:
            # A typo here would produce a bar that can never fire, which reads
            # as a configured control and is not one.
            raise ValueError(
                f"judgement_requires_any names {', '.join(unknown)}, which "
                "no review has. A field nothing carries is a bar nothing can clear"
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
        judgement_requires_any=tuple(raw.get("judgement_requires_any", ())),
    )
