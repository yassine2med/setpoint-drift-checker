"""Command line entry: python -m setpoint_drift TREND.csv"""

import argparse
import sys

from .checks import Thresholds, check_all
from .data import load_samples


def main(argv: list[str] | None = None) -> int:
    """Print findings; return 1 when any exist, 0 when none, 2 on bad input."""
    defaults = Thresholds()
    parser = argparse.ArgumentParser(prog="setpoint_drift", description="Flag setpoint drift in trend data.")
    parser.add_argument("file")
    parser.add_argument("--offset", type=float, default=defaults.offset)
    parser.add_argument("--creep-per-day", type=float, default=defaults.creep_per_day)
    parser.add_argument("--tracking-band", type=float, default=defaults.tracking_band)
    parser.add_argument("--min-run", type=int, default=defaults.min_run)
    parser.add_argument("--max-changes-per-day", type=int, default=defaults.max_changes_per_day)
    args = parser.parse_args(argv)
    limits = Thresholds(args.offset, args.creep_per_day, args.tracking_band,
                        args.min_run, args.max_changes_per_day)
    try:
        groups = load_samples(args.file)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    findings = check_all(groups, limits)
    for finding in findings:
        print(finding)
    print(f"{len(groups)} point(s) checked, {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
