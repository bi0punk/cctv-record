from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.utils import (
    seconds_until_next_hour,
    segment_filename,
    build_output_path,
    crop_filter,
    halves_for_split,
)


class TestSecondsUntilNextHour:
    def test_exact_hour_returns_3600(self, monkeypatch):
        fixed = datetime(2026, 6, 23, 10, 0, 0, 0, tzinfo=timezone.utc).astimezone()
        monkeypatch.setattr("app.utils._now", lambda: fixed)
        assert seconds_until_next_hour() == 3600

    def test_15_minutes_before(self, monkeypatch):
        fixed = datetime(2026, 6, 23, 10, 45, 0, 0, tzinfo=timezone.utc).astimezone()
        monkeypatch.setattr("app.utils._now", lambda: fixed)
        assert seconds_until_next_hour() == 900

    def test_1_second_before(self, monkeypatch):
        fixed = datetime(2026, 6, 23, 10, 59, 59, 0, tzinfo=timezone.utc).astimezone()
        monkeypatch.setattr("app.utils._now", lambda: fixed)
        assert seconds_until_next_hour() == 1


class TestSegmentFilename:
    def test_partial(self):
        dt = datetime(2026, 6, 23, 15, 30, 15)
        assert segment_filename(dt, is_partial=True) == "15_30_15"

    def test_full_hour(self):
        dt = datetime(2026, 6, 23, 15, 30, 15)
        assert segment_filename(dt, is_partial=False) == "16_00_00"

    def test_full_hour_at_boundary(self):
        dt = datetime(2026, 6, 23, 15, 59, 59)
        assert segment_filename(dt, is_partial=False) == "16_00_00"


class TestBuildOutputPath:
    def test_constructs_path(self):
        base = Path("/recordings")
        dt = datetime(2026, 6, 23, 15, 30, 0)
        result = build_output_path(base, "Entrada", dt)
        assert result == Path("/recordings/2026/06/23/Entrada")


class TestCropFilter:
    def test_vertical_left(self):
        assert crop_filter("vertical", "L") == "crop=iw/2:ih:0:0"

    def test_vertical_right(self):
        assert crop_filter("vertical", "R") == "crop=iw/2:ih:iw/2:0"

    def test_horizontal_top(self):
        assert crop_filter("horizontal", "T") == "crop=iw:ih/2:0:0"

    def test_horizontal_bottom(self):
        assert crop_filter("horizontal", "B") == "crop=iw:ih/2:0:ih/2"

    def test_none_returns_none(self):
        assert crop_filter("none", "L") is None

    def test_invalid_split(self):
        assert crop_filter("unknown", "L") is None


class TestHalvesForSplit:
    def test_vertical(self):
        result = halves_for_split("vertical")
        assert result == [
            ("L", "crop=iw/2:ih:0:0"),
            ("R", "crop=iw/2:ih:iw/2:0"),
        ]

    def test_horizontal(self):
        result = halves_for_split("horizontal")
        assert result == [
            ("T", "crop=iw:ih/2:0:0"),
            ("B", "crop=iw:ih/2:0:ih/2"),
        ]

    def test_none(self):
        assert halves_for_split("none") == [("", "")]
