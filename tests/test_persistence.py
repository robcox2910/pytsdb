"""Tests for JSON persistence."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pytsdb.database import TimeSeriesDB
from pytsdb.errors import PersistenceError, PyTSDBError
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
        """Loading a non-existent file raises PersistenceError."""
        with pytest.raises(PersistenceError):
            load(tmp_path / "nope.json")

    def test_load_bad_json_raises(self, tmp_path: Path) -> None:
        """Loading a file with non-object JSON should raise TypeError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("[]", encoding="utf-8")
        with pytest.raises(PersistenceError, match="top level"):
            load(bad_file)


class _SimulatedCrashError(OSError):
    """Stands in for the power going out part-way through a save."""


def test_interrupted_save_keeps_the_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a crash mid-save used to leave a truncated, unloadable file."""
    db = TimeSeriesDB()
    db.create_series("a")
    path = tmp_path / "data.json"
    save(db, path)
    before = path.read_bytes()
    db.create_series("b")

    def write_half_then_crash(self: Path, data: str, *_args: object, **_kwargs: object) -> int:
        with self.open("w", encoding="utf-8") as handle:
            handle.write(data[: len(data) // 2])
        raise _SimulatedCrashError

    def crash(*_args: object) -> None:
        raise _SimulatedCrashError

    monkeypatch.setattr(Path, "write_text", write_half_then_crash)
    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(_SimulatedCrashError):
        save(db, path)
    monkeypatch.undo()
    assert path.read_bytes() == before
    load(path)
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


class TestUnreadableSaveFiles:
    """A missing or damaged save file raises PersistenceError, naming the file."""

    def test_missing_file_raises_persistence_error(self, tmp_path: Path) -> None:
        """Loading a file that isn't there is a PersistenceError."""
        with pytest.raises(PersistenceError, match=r"missing\.json"):
            load(tmp_path / "missing.json")

    def test_bad_json_raises_persistence_error_naming_the_file(self, tmp_path: Path) -> None:
        """A scribbled-on file is a PersistenceError that names the file."""
        path = tmp_path / "saved.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(PersistenceError, match=r"saved\.json"):
            load(path)

    def test_wrong_shape_raises_persistence_error(self, tmp_path: Path) -> None:
        """Valid JSON that isn't a saved database is a PersistenceError."""
        path = tmp_path / "saved.json"
        path.write_text('{"something": "else"}', encoding="utf-8")
        with pytest.raises(PersistenceError, match=r"saved\.json"):
            load(path)

    def test_persistence_error_is_part_of_the_library_errors(self) -> None:
        """PersistenceError belongs to the library's own family of errors."""
        assert issubclass(PersistenceError, PyTSDBError)


class TestJunkSaveFiles:
    """Regressions: files the property tests found that escaped as other errors."""

    def test_bytes_that_are_not_text_raise_persistence_error(self, tmp_path: Path) -> None:
        """A file that isn't UTF-8 text used to escape as UnicodeDecodeError."""
        path = tmp_path / "db.json"
        path.write_bytes(b"\x80")
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)

    def test_number_too_long_to_read_raises_persistence_error(self, tmp_path: Path) -> None:
        """A 5,000-digit number used to escape as a plain ValueError."""
        path = tmp_path / "db.json"
        path.write_text("1" * 5000, encoding="utf-8")
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)

    def test_nesting_too_deep_raises_persistence_error(self, tmp_path: Path) -> None:
        """100,000 opening brackets used to escape as RecursionError."""
        path = tmp_path / "db.json"
        path.write_text("[" * 100_000, encoding="utf-8")
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)

    def test_retention_too_long_for_timedelta_raises_persistence_error(
        self, tmp_path: Path
    ) -> None:
        """A retention period past timedelta's limit used to escape as OverflowError."""
        path = tmp_path / "db.json"
        path.write_text(
            '{"series": {}, "retention": {"": {"max_age_seconds": 86400000000000.0}}}',
            encoding="utf-8",
        )
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)

    def test_zero_retention_raises_persistence_error(self, tmp_path: Path) -> None:
        """A retention period of zero used to escape as InvalidRetentionError."""
        path = tmp_path / "db.json"
        path.write_text(
            '{"series": {}, "retention": {"": {"max_age_seconds": false}}}', encoding="utf-8"
        )
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)

    def test_reading_too_big_for_a_float_raises_persistence_error(self, tmp_path: Path) -> None:
        """A 400-digit reading used to escape as OverflowError."""
        path = tmp_path / "db.json"
        point = '{"timestamp": "2024-07-04T10:00:00+00:00", "value": 1' + "0" * 400 + "}"
        path.write_text(
            '{"series": {"t": {"name": "t", "points": [' + point + "]}}}", encoding="utf-8"
        )
        with pytest.raises(PersistenceError, match=r"db\.json"):
            load(path)
