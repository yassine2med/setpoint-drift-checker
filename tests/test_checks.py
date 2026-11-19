from datetime import datetime, timedelta
from pathlib import Path

import pytest

from setpoint_drift import Sample, Thresholds, check_all, check_point, load_samples
from setpoint_drift.__main__ import main

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "zone_trend.csv"
START = datetime(2026, 7, 1)


def make(setpoints, values=None, step_hours=1):
    values = values or setpoints
    return [Sample(START + timedelta(hours=i * step_hours), sp, v)
            for i, (sp, v) in enumerate(zip(setpoints, values))]


def checks(samples, **limits):
    return [f.check for f in check_point("P", samples, Thresholds(**limits))]


def test_steady_point_is_clean():
    assert checks(make([72.0] * 24)) == []


def test_empty_and_single_sample():
    assert check_point("P", []) == []
    assert checks(make([72.0])) == []


def test_offset_run_is_flagged():
    sps = [72.0] * 10 + [68.0] * 5 + [72.0] * 10
    assert "D1" in checks(make(sps))


def test_short_offset_is_ignored():
    sps = [72.0] * 10 + [68.0] * 3 + [72.0] * 10
    assert "D1" not in checks(make(sps))


def test_offset_inside_tolerance_is_ignored():
    sps = [72.0] * 10 + [72.8] * 6 + [72.0] * 10
    assert "D1" not in checks(make(sps))


def test_creep_upward_and_downward():
    up = [72 + 0.5 * (i // 24) for i in range(72)]
    down = [72 - 0.5 * (i // 24) for i in range(72)]
    assert "D2" in checks(make(up))
    assert "D2" in checks(make(down))


def test_no_creep_on_short_trend():
    assert "D2" not in checks(make([72.0, 72.5, 73.0], step_hours=1))


def test_tracking_error_run():
    values = [72.0] * 5 + [76.0] * 6 + [72.0] * 5
    assert "D3" in checks(make([72.0] * 16, values))


def test_tracking_error_negative_side():
    values = [72.0] * 5 + [68.0] * 6 + [72.0] * 5
    assert "D3" in checks(make([72.0] * 16, values))


def test_tracking_band_option():
    values = [72.0] * 5 + [73.5] * 6 + [72.0] * 5
    assert "D3" not in checks(make([72.0] * 16, values))
    assert "D3" in checks(make([72.0] * 16, values), tracking_band=1.0)


def test_chatter_counts_changes_per_day():
    sps = [72.0, 73.0] * 6 + [72.0] * 12
    found = check_point("P", make(sps), Thresholds(max_changes_per_day=4))
    assert [f.check for f in found].count("D4") == 1
    assert found[-1].detail.endswith("on 2026-07-01")


def test_finding_text_contains_point_and_check():
    finding = check_point("Z1", make([72.0] * 5 + [76.0] * 5, [72.0] * 5 + [72.0] * 5))[0]
    assert str(finding).startswith(f"{finding.check} Z1:")


def test_load_samples_groups_and_sorts(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text(
        "timestamp,point,setpoint,value\n"
        "2026-07-01T01:00:00,B,72,72\n2026-07-01T00:00:00,B,72,71.5\n"
        "2026-07-01T00:00:00,A,70,70\n2026-07-01T02:00:00,A,,70\n",
        encoding="utf-8",
    )
    groups = load_samples(path)
    assert sorted(groups) == ["A", "B"]
    assert groups["B"][0].value == 71.5
    assert len(groups["A"]) == 1  # the blank setpoint row is skipped


def test_load_samples_errors(tmp_path):
    bad_columns = tmp_path / "a.csv"
    bad_columns.write_text("timestamp,point\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_samples(bad_columns)
    bad_time = tmp_path / "b.csv"
    bad_time.write_text("timestamp,point,setpoint,value\nyesterday,A,70,70\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bad timestamp"):
        load_samples(bad_time)


def test_example_findings():
    found = {(f.point.split(".")[1], f.check) for f in check_all(load_samples(EXAMPLE))}
    assert found == {("ZONE101", "D2"), ("ZONE103", "D1"), ("ZONE104", "D3"), ("ZONE105", "D4")}


def test_cli(tmp_path, capsys):
    assert main([str(EXAMPLE)]) == 1
    assert "5 point(s) checked, 4 finding(s)" in capsys.readouterr().out
    assert main([str(EXAMPLE), "--offset", "10", "--creep-per-day", "10", "--tracking-band", "10",
                 "--max-changes-per-day", "99"]) == 0
    assert main([str(tmp_path / "none.csv")]) == 2
