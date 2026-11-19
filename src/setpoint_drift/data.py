"""Read a long format trend CSV: timestamp, point, setpoint, value."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

COLUMNS = ("timestamp", "point", "setpoint", "value")


@dataclass(frozen=True)
class Sample:
    """One reading of a controlled point."""

    when: datetime
    setpoint: float
    value: float


def load_samples(path: str | Path) -> dict[str, list[Sample]]:
    """Load samples grouped by point and sorted by time.

    Rows with a blank or non numeric setpoint or value are skipped.
    Raises ValueError when a column or a timestamp is bad.
    """
    groups: dict[str, list[Sample]] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("missing columns: " + ", ".join(missing))
        for line, raw in enumerate(reader, start=2):
            try:
                when = datetime.fromisoformat(raw["timestamp"])
            except ValueError as err:
                raise ValueError(f"line {line}: bad timestamp '{raw['timestamp']}'") from err
            try:
                sample = Sample(when, float(raw["setpoint"]), float(raw["value"]))
            except (TypeError, ValueError):
                continue
            groups.setdefault(raw["point"], []).append(sample)
    for samples in groups.values():
        samples.sort(key=lambda s: s.when)
    return groups
