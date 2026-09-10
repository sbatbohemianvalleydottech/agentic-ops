import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

DEFAULTS = Path(__file__).parent / "thresholds.toml"


@dataclass(frozen=True)
class Thresholds:
    idle_ceiling: float
    target_floor: float
    oversize_ratio: float
    cold_after_days: int
    stale_after_days: int
    weekend_ratio: float
    annualisation_multiplier: Decimal
    owner_tag_keys: tuple[str, ...]


def load_thresholds(path: Path | None = None) -> Thresholds:
    """Read the reviewable threshold config.

    TOML via stdlib `tomllib`, so the core acquires no dependency and stays
    importable and testable with nothing installed.
    """
    raw = tomllib.loads((path or DEFAULTS).read_text())

    return Thresholds(
        idle_ceiling=float(raw["idle_ceiling"]),
        target_floor=float(raw["target_floor"]),
        oversize_ratio=float(raw["oversize_ratio"]),
        cold_after_days=int(raw["cold_after_days"]),
        stale_after_days=int(raw["stale_after_days"]),
        weekend_ratio=float(raw["weekend_ratio"]),
        # Quoted in the file and parsed here, so the multiplier that scales every
        # headline figure never passes through a float.
        annualisation_multiplier=Decimal(str(raw["annualisation_multiplier"])),
        owner_tag_keys=tuple(raw["owner_tag_keys"]),
    )
