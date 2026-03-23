"""Tests for JSON persistence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pytsdb.database import TimeSeriesDB
from pytsdb.persistence import load, save

YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
HOUR_10 = 10
TEMP_LOW = 68.0
TEMP_MID = 72.5
ONE_DAY = timedelta(days=1)


def _ts(hour: int = HOUR_10) -> datetime:
    """Create a UTC timestamp on July 4, 2024."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, 0, tzinfo=UTC)


class TestPersistence:
    """Test save/load round-trip to JSON."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Save a database and load it back."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts())
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(12))
        db.set_retention("temp", max_age=ONE_DAY)

        file_path = tmp_path / "db.json"
        save(db, file_path)
        assert file_path.exists()

        restored = load(file_path)
        assert restored.list_series() == ["temp"]
        points = restored.query("temp")
        assert len(points) == 2  # noqa: PLR2004
        assert points[0].value == TEMP_LOW

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Save should create intermediate directories."""
        db = TimeSeriesDB()
        db.create_series("temp")
        nested = tmp_path / "a" / "b" / "db.json"
        save(db, nested)
        assert nested.exists()

    def test_load_missing_file_raises(self, tmp_path: Path) -> None:
        """Loading a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load(tmp_path / "nope.json")

    def test_load_bad_json_raises(self, tmp_path: Path) -> None:
        """Loading a file with non-object JSON should raise TypeError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("[]", encoding="utf-8")
        with pytest.raises(TypeError, match="Top-level"):
            load(bad_file)
