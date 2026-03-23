"""Tests for the TimeSeriesDB class."""

from datetime import UTC, datetime, timedelta

import pytest

from pytsdb.aggregation import AggFunc
from pytsdb.database import TimeSeriesDB
from pytsdb.errors import DuplicateSeriesError, SeriesNotFoundError

YEAR_2024 = 2024
MONTH_JULY = 7
DAY_1 = 1
DAY_4 = 4
DAY_10 = 10
HOUR_9 = 9
HOUR_10 = 10
HOUR_11 = 11
HOUR_12 = 12
ONE_HOUR = timedelta(hours=1)
ONE_DAY = timedelta(days=1)
TEMP_LOW = 68.0
TEMP_MID = 72.5
TEMP_HIGH = 75.0
EXPECTED_AVG = 71.5
EXPECTED_RATE = 0.00125  # (72.5 - 68.0) / 3600


def _ts(hour: int, day: int = DAY_4) -> datetime:
    """Create a UTC timestamp in July 2024."""
    return datetime(YEAR_2024, MONTH_JULY, day, hour, 0, tzinfo=UTC)


class TestSeriesCRUD:
    """Test creating, listing, and deleting series."""

    def test_create_series(self) -> None:
        """Create a new series and verify it exists."""
        db = TimeSeriesDB()
        series = db.create_series("temp")
        assert series.name == "temp"
        assert db.series_count == 1

    def test_duplicate_series_raises(self) -> None:
        """Creating a series with a duplicate name should raise."""
        db = TimeSeriesDB()
        db.create_series("temp")
        with pytest.raises(DuplicateSeriesError):
            db.create_series("temp")

    def test_get_series(self) -> None:
        """Retrieve a series by name."""
        db = TimeSeriesDB()
        db.create_series("temp")
        series = db.get_series("temp")
        assert series.name == "temp"

    def test_get_missing_raises(self) -> None:
        """Getting a non-existent series should raise."""
        db = TimeSeriesDB()
        with pytest.raises(SeriesNotFoundError):
            db.get_series("nope")

    def test_delete_series(self) -> None:
        """Delete a series and verify it's gone."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.delete_series("temp")
        assert db.series_count == 0

    def test_delete_missing_raises(self) -> None:
        """Deleting a non-existent series should raise."""
        db = TimeSeriesDB()
        with pytest.raises(SeriesNotFoundError):
            db.delete_series("nope")

    def test_list_series(self) -> None:
        """List series names in alphabetical order."""
        db = TimeSeriesDB()
        db.create_series("humidity")
        db.create_series("temperature")
        db.create_series("pressure")
        assert db.list_series() == ["humidity", "pressure", "temperature"]


class TestDataOperations:
    """Test adding and querying data through the DB."""

    def test_add_and_query(self) -> None:
        """Add points and query them back."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(HOUR_12))
        points = db.query("temp")
        assert len(points) == 2  # noqa: PLR2004

    def test_add_to_missing_raises(self) -> None:
        """Adding to a non-existent series should raise."""
        db = TimeSeriesDB()
        with pytest.raises(SeriesNotFoundError):
            db.add_point("nope", value=TEMP_LOW)

    def test_query_with_time_range(self) -> None:
        """Query with start/end bounds."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_9))
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(HOUR_10))
        db.add_point("temp", value=TEMP_HIGH, timestamp=_ts(HOUR_11))
        result = db.query("temp", start=_ts(HOUR_10), end=_ts(HOUR_10))
        assert len(result) == 1
        assert result[0].value == TEMP_MID

    def test_query_with_tags(self) -> None:
        """Query filtering by tags."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10), tags={"room": "kitchen"})
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(HOUR_11), tags={"room": "bedroom"})
        result = db.query("temp", tags={"room": "kitchen"})
        assert len(result) == 1
        assert result[0].value == TEMP_LOW


class TestAggregation:
    """Test aggregation through the DB."""

    def test_hourly_avg(self) -> None:
        """Aggregate hourly averages."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        db.add_point("temp", value=TEMP_HIGH, timestamp=_ts(HOUR_10))
        result = db.aggregate("temp", window=ONE_HOUR, func=AggFunc.AVG)
        assert len(result) == 1
        assert result[0].value == pytest.approx(EXPECTED_AVG)

    def test_aggregate_empty_returns_empty(self) -> None:
        """Aggregating an empty series should return empty list."""
        db = TimeSeriesDB()
        db.create_series("temp")
        result = db.aggregate("temp", window=ONE_HOUR)
        assert result == []


class TestDownsampling:
    """Test downsampling through the DB."""

    def test_downsample(self) -> None:
        """Downsample through the DB facade."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        db.add_point("temp", value=TEMP_HIGH, timestamp=_ts(HOUR_10))
        result = db.downsample("temp", target_interval=ONE_HOUR)
        assert len(result) == 1


class TestRateOfChange:
    """Test rate-of-change computation."""

    def test_basic_rate(self) -> None:
        """Compute rate between two points (units per second)."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(HOUR_11))
        result = db.rate_of_change("temp")
        assert len(result) == 1
        assert result[0].value == pytest.approx(EXPECTED_RATE)

    def test_empty_series(self) -> None:
        """Rate of change on empty series returns empty list."""
        db = TimeSeriesDB()
        db.create_series("temp")
        assert db.rate_of_change("temp") == []

    def test_single_point(self) -> None:
        """Rate of change with one point returns empty list."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        assert db.rate_of_change("temp") == []


class TestRetention:
    """Test retention policy through the DB."""

    def test_apply_retention(self) -> None:
        """Old points should be removed after applying retention."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10, day=DAY_1))
        db.add_point("temp", value=TEMP_MID, timestamp=_ts(HOUR_10, day=DAY_10))
        db.set_retention("temp", max_age=timedelta(days=5))
        now = _ts(HOUR_10, day=DAY_10)
        removed = db.apply_retention(now=now)
        assert removed == 1
        series = db.get_series("temp")
        assert len(series) == 1

    def test_set_retention_missing_raises(self) -> None:
        """Setting retention on a missing series should raise."""
        db = TimeSeriesDB()
        with pytest.raises(SeriesNotFoundError):
            db.set_retention("nope", max_age=ONE_DAY)

    def test_delete_series_removes_retention(self) -> None:
        """Deleting a series should also remove its retention policy."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.set_retention("temp", max_age=ONE_DAY)
        db.delete_series("temp")
        # Re-create and verify no retention set
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10, day=DAY_1))
        removed = db.apply_retention(now=_ts(HOUR_10, day=DAY_10))
        assert removed == 0


class TestDatabaseSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        """Serialize and deserialize the full database."""
        db = TimeSeriesDB()
        db.create_series("temp")
        db.add_point("temp", value=TEMP_LOW, timestamp=_ts(HOUR_10))
        db.set_retention("temp", max_age=ONE_DAY)

        restored = TimeSeriesDB.from_dict(db.to_dict())
        assert restored.list_series() == ["temp"]
        points = restored.query("temp")
        assert len(points) == 1
        assert points[0].value == TEMP_LOW

    def test_from_dict_bad_series_type(self) -> None:
        """Raise TypeError if series is not a dict."""
        with pytest.raises(TypeError, match="series"):
            TimeSeriesDB.from_dict({"series": "bad"})

    def test_from_dict_bad_retention_type(self) -> None:
        """Raise TypeError if retention is not a dict."""
        with pytest.raises(TypeError, match="retention"):
            TimeSeriesDB.from_dict({"series": {}, "retention": "bad"})
