"""Tests for aggregation functions."""

from datetime import UTC, datetime, timedelta

import pytest

from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.datapoint import DataPoint
from pytsdb.errors import EmptySeriesError, InvalidWindowError

YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
ONE_HOUR = timedelta(hours=1)
TWO_HOURS = timedelta(hours=2)
VALUE_10 = 10.0
VALUE_20 = 20.0
VALUE_30 = 30.0
VALUE_40 = 40.0
EXPECTED_AVG_10_20 = 15.0
EXPECTED_SUM_10_20 = 30.0
EXPECTED_AVG_30_40 = 35.0
NUM_POINTS_PER_BUCKET = 2.0


def _ts(hour: int, minute: int = 0) -> datetime:
    """Create a UTC timestamp on July 4, 2024."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, minute, tzinfo=UTC)


def _sample_points() -> list[DataPoint]:
    """Create points at 9:00, 9:30, 10:00, 10:30."""
    return [
        DataPoint(timestamp=_ts(9, 0), value=VALUE_10),
        DataPoint(timestamp=_ts(9, 30), value=VALUE_20),
        DataPoint(timestamp=_ts(10, 0), value=VALUE_30),
        DataPoint(timestamp=_ts(10, 30), value=VALUE_40),
    ]


class TestAggregateAvg:
    """Test average aggregation."""

    def test_hourly_avg(self) -> None:
        """Average over one-hour windows."""
        pts = _sample_points()
        result = aggregate(pts, window=ONE_HOUR, func=AggFunc.AVG)
        assert len(result) == 2  # noqa: PLR2004
        assert result[0].value == pytest.approx(EXPECTED_AVG_10_20)
        assert result[1].value == pytest.approx(EXPECTED_AVG_30_40)

    def test_two_hour_avg(self) -> None:
        """A wider window produces fewer buckets (epoch-aligned)."""
        pts = _sample_points()
        result = aggregate(pts, window=TWO_HOURS, func=AggFunc.AVG)
        # Epoch-aligned 2h buckets: 8:00-10:00 has 9:00+9:30, 10:00-12:00 has 10:00+10:30
        expected_count = 2
        assert len(result) == expected_count
        expected_first = (VALUE_10 + VALUE_20) / expected_count
        expected_second = (VALUE_30 + VALUE_40) / expected_count
        assert result[0].value == pytest.approx(expected_first)
        assert result[1].value == pytest.approx(expected_second)


class TestAggregateMinMaxSumCount:
    """Test min, max, sum, and count aggregations."""

    def test_min(self) -> None:
        """Min should return the smallest value per window."""
        pts = _sample_points()
        result = aggregate(pts, window=ONE_HOUR, func=AggFunc.MIN)
        assert result[0].value == pytest.approx(VALUE_10)
        assert result[1].value == pytest.approx(VALUE_30)

    def test_max(self) -> None:
        """Max should return the largest value per window."""
        pts = _sample_points()
        result = aggregate(pts, window=ONE_HOUR, func=AggFunc.MAX)
        assert result[0].value == pytest.approx(VALUE_20)
        assert result[1].value == pytest.approx(VALUE_40)

    def test_sum(self) -> None:
        """Sum should total all values per window."""
        pts = _sample_points()
        result = aggregate(pts, window=ONE_HOUR, func=AggFunc.SUM)
        assert result[0].value == pytest.approx(EXPECTED_SUM_10_20)

    def test_count(self) -> None:
        """Count should return the number of points per window."""
        pts = _sample_points()
        result = aggregate(pts, window=ONE_HOUR, func=AggFunc.COUNT)
        assert result[0].value == pytest.approx(NUM_POINTS_PER_BUCKET)


class TestAggregateErrors:
    """Test error conditions."""

    def test_empty_list_raises(self) -> None:
        """Aggregating an empty list should raise EmptySeriesError."""
        with pytest.raises(EmptySeriesError):
            aggregate([], window=ONE_HOUR)

    def test_zero_window_raises(self) -> None:
        """A zero-duration window should raise InvalidWindowError."""
        pts = _sample_points()
        with pytest.raises(InvalidWindowError):
            aggregate(pts, window=timedelta(0))

    def test_negative_window_raises(self) -> None:
        """A negative window should raise InvalidWindowError."""
        pts = _sample_points()
        with pytest.raises(InvalidWindowError):
            aggregate(pts, window=timedelta(hours=-1))
