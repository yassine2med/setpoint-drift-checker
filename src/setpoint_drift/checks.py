"""Four checks on one point's samples.

D1 offset   setpoint sits away from the point's usual (median) setpoint for a while.
D2 creep    setpoint moves steadily in one direction across the whole trend.
D3 tracking measured value stays away from the setpoint for a while.
D4 chatter  setpoint changes too many times in one calendar day.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Callable

from .data import Sample


@dataclass(frozen=True)
class Thresholds:
    """Limits used by the checks. Units follow the trend data (for example degF)."""

    offset: float = 1.0          # D1: allowed distance from the median setpoint
    creep_per_day: float = 0.25  # D2: slope that counts as creep
    tracking_band: float = 2.0   # D3: allowed |value - setpoint|
    min_run: int = 4             # D1 and D3: consecutive samples required
    max_changes_per_day: int = 4  # D4


@dataclass(frozen=True)
class Finding:
    """One finding for a point."""

    point: str
    check: str
    detail: str

    def __str__(self) -> str:
        return f"{self.check} {self.point}: {self.detail}"


def _runs(flags: list[bool], min_run: int) -> list[tuple[int, int]]:
    """Return (first, last) index pairs of True runs at least `min_run` long."""
    runs, start = [], None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start >= min_run:
                runs.append((start, i - 1))
            start = None
    return runs


def _slope_per_day(samples: list[Sample]) -> float:
    """Least squares slope of setpoint against time, in units per day."""
    t0 = samples[0].when
    xs = [(s.when - t0).total_seconds() / 86400 for s in samples]
    ys = [s.setpoint for s in samples]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom


def check_point(point: str, samples: list[Sample], limits: Thresholds = Thresholds()) -> list[Finding]:
    """Run all four checks on one point and return its findings."""
    if not samples:
        return []
    found: list[Finding] = []
    usual = median(s.setpoint for s in samples)

    def episodes(check: str, test: Callable[[Sample], bool], label: Callable[[Sample], str]) -> None:
        for first, last in _runs([test(s) for s in samples], limits.min_run):
            found.append(Finding(point, check,
                                 f"{label(samples[first])} from {samples[first].when:%Y-%m-%d %H:%M} "
                                 f"to {samples[last].when:%Y-%m-%d %H:%M} ({last - first + 1} samples)"))

    episodes("D1", lambda s: abs(s.setpoint - usual) > limits.offset,
             lambda s: f"setpoint {s.setpoint:g} vs usual {usual:g}")
    if len(samples) > 1:
        slope = _slope_per_day(samples)
        span_days = (samples[-1].when - samples[0].when).total_seconds() / 86400
        if abs(slope) >= limits.creep_per_day and abs(slope) * span_days > limits.offset:
            found.append(Finding(point, "D2", f"setpoint creeping {slope:+.2f} per day "
                                              f"({abs(slope) * span_days:.1f} over the trend)"))
    episodes("D3", lambda s: abs(s.value - s.setpoint) > limits.tracking_band,
             lambda s: f"value off setpoint by more than {limits.tracking_band:g}")

    changes: dict[str, int] = {}
    for prev, cur in zip(samples, samples[1:]):
        if cur.setpoint != prev.setpoint:
            day = f"{cur.when:%Y-%m-%d}"
            changes[day] = changes.get(day, 0) + 1
    for day, count in sorted(changes.items()):
        if count > limits.max_changes_per_day:
            found.append(Finding(point, "D4", f"{count} setpoint changes on {day}"))
    return found


def check_all(groups: dict[str, list[Sample]], limits: Thresholds = Thresholds()) -> list[Finding]:
    """Check every point, ordered by point name."""
    return [f for name in sorted(groups) for f in check_point(name, groups[name], limits)]
