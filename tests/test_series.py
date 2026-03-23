"""Tests for the TimeSeries class."""

from datetime import UTC, datetime

import pytest

from pytsdb.datapoint import DataPoint
from pytsdb.errors import EmptySeriesError
from pytsdb.series import TimeSeries

TEMP_HIGH = 75.0
TEMP_MID = 72.5
TEMP_LOW = 68.0
EXPECTED_COUNT_TWO = 2
YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
HOUR_10 = 10
HOUR_12 = 12
HOUR_14 = 14


def _ts(hour: int) -> datetime:
    """Create a UTC timestamp on July 4, 2024 at the given hour."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, 0, tzinfo=UTC)


class TestTimeSeriesBasics:
    """Test basic TimeSeries operations."""

    def test_new_series_is_empty(self) -> None:
        """A freshly created series should have zero points."""
        series = TimeSeries("temp")
        assert len(series) == 0

    def test_add_point(self) -> None:
        """Adding a point should increase the length."""
        series = TimeSeries("temp")
        series.add(DataPoint(timestamp=_ts(HOUR_10), value=TEMP_MID))
        assert len(series) == 1

    def test_points_stay_sorted(self) -> None:
        """Points should be in chronological order regardless of insertion order."""
        series = TimeSeries("temp")
        series.add(DataPoint(timestamp=_ts(HOUR_14), value=TEMP_HIGH))
        series.add(DataPoint(timestamp=_ts(HOUR_10), value=TEMP_LOW))
        series.add(DataPoint(timestamp=_ts(HOUR_12), value=TEMP_MID))
        timestamps = [p.timestamp for p in series]
        assert timestamps == [_ts(HOUR_10), _ts(HOUR_12), _ts(HOUR_14)]

    def test_add_value_convenience(self) -> None:
        """The add_value helper should create and insert a point."""
        series = TimeSeries("temp")
        dp = series.add_value(TEMP_MID, timestamp=_ts(HOUR_10), tags={"room": "kitchen"})
        assert dp.value == TEMP_MID
        assert len(series) == 1

    def test_iteration(self) -> None:
        """Iterating should yield points in chronological order."""
        series = TimeSeries("temp")
        series.add_value(TEMP_HIGH, timestamp=_ts(HOUR_14))
        series.add_value(TEMP_LOW, timestamp=_ts(HOUR_10))
        values = [p.value for p in series]
        assert values == [TEMP_LOW, TEMP_HIGH]


class TestTimeSeriesFirstLast:
    """Test the first/last properties."""

    def test_first(self) -> None:
        """Return the oldest point."""
        series = TimeSeries("temp")
        series.add_value(TEMP_HIGH, timestamp=_ts(HOUR_14))
        series.add_value(TEMP_LOW, timestamp=_ts(HOUR_10))
        assert series.first.value == TEMP_LOW

    def test_last(self) -> None:
        """Return the newest point."""
        series = TimeSeries("temp")
        series.add_value(TEMP_HIGH, timestamp=_ts(HOUR_14))
        series.add_value(TEMP_LOW, timestamp=_ts(HOUR_10))
        assert series.last.value == TEMP_HIGH

    def test_first_empty_raises(self) -> None:
        """Raise EmptySeriesError when series has no points."""
        series = TimeSeries("temp")
        with pytest.raises(EmptySeriesError):
            _ = series.first

    def test_last_empty_raises(self) -> None:
        """Raise EmptySeriesError when series has no points."""
        series = TimeSeries("temp")
        with pytest.raises(EmptySeriesError):
            _ = series.last


class TestTimeSeriesClear:
    """Test clearing a series."""

    def test_clear(self) -> None:
        """Clear should remove all points."""
        series = TimeSeries("temp")
        series.add_value(TEMP_MID, timestamp=_ts(HOUR_10))
        series.clear()
        assert len(series) == 0


class TestTimeSeriesSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        """Serializing and deserializing should preserve data."""
        series = TimeSeries("temp")
        series.add_value(TEMP_MID, timestamp=_ts(HOUR_10), tags={"room": "kitchen"})
        series.add_value(TEMP_HIGH, timestamp=_ts(HOUR_14))

        restored = TimeSeries.from_dict(series.to_dict())
        assert restored.name == "temp"
        assert len(restored) == EXPECTED_COUNT_TWO
        assert restored.first.value == TEMP_MID

    def test_from_dict_bad_name(self) -> None:
        """Raise TypeError if name is not a string."""
        with pytest.raises(TypeError, match="name"):
            TimeSeries.from_dict({"name": 123, "points": []})

    def test_from_dict_bad_points(self) -> None:
        """Raise TypeError if points is not a list."""
        with pytest.raises(TypeError, match="points"):
            TimeSeries.from_dict({"name": "temp", "points": "bad"})

    def test_from_dict_bad_point_item(self) -> None:
        """Raise TypeError if a point entry is not a dict."""
        with pytest.raises(TypeError, match="each point"):
            TimeSeries.from_dict({"name": "temp", "points": ["bad"]})
