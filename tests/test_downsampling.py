"""Tests for downsampling."""

from datetime import UTC, datetime, timedelta

import pytest

from pytsdb.aggregation import AggFunc
from pytsdb.datapoint import DataPoint
from pytsdb.downsampling import downsample
from pytsdb.errors import InvalidWindowError

YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
ONE_HOUR = timedelta(hours=1)
VALUE_10 = 10.0
VALUE_20 = 20.0
VALUE_30 = 30.0
VALUE_40 = 40.0
EXPECTED_AVG_10_20 = 15.0
EXPECTED_AVG_30_40 = 35.0


def _ts(hour: int, minute: int = 0) -> datetime:
    """Create a UTC timestamp on July 4, 2024."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, minute, tzinfo=UTC)


def _sample_points() -> list[DataPoint]:
    """Create four half-hourly points spanning two hours."""
    return [
        DataPoint(timestamp=_ts(9, 0), value=VALUE_10),
        DataPoint(timestamp=_ts(9, 30), value=VALUE_20),
        DataPoint(timestamp=_ts(10, 0), value=VALUE_30),
        DataPoint(timestamp=_ts(10, 30), value=VALUE_40),
    ]


class TestDownsample:
    """Test resolution reduction."""

    def test_half_hourly_to_hourly(self) -> None:
        """Downsample half-hourly to hourly averages."""
        pts = _sample_points()
        result = downsample(pts, target_interval=ONE_HOUR)
        assert len(result) == 2  # noqa: PLR2004
        assert result[0].value == pytest.approx(EXPECTED_AVG_10_20)
        assert result[1].value == pytest.approx(EXPECTED_AVG_30_40)

    def test_downsample_with_max(self) -> None:
        """Downsample using MAX function."""
        pts = _sample_points()
        result = downsample(pts, target_interval=ONE_HOUR, func=AggFunc.MAX)
        assert result[0].value == pytest.approx(VALUE_20)
        assert result[1].value == pytest.approx(VALUE_40)

    def test_empty_list(self) -> None:
        """Downsampling an empty list should return an empty list."""
        result = downsample([], target_interval=ONE_HOUR)
        assert result == []

    def test_invalid_interval_raises(self) -> None:
        """A zero-duration interval should raise InvalidWindowError."""
        pts = _sample_points()
        with pytest.raises(InvalidWindowError):
            downsample(pts, target_interval=timedelta(0))

    def test_negative_interval_raises(self) -> None:
        """A negative interval should raise InvalidWindowError."""
        pts = _sample_points()
        with pytest.raises(InvalidWindowError):
            downsample(pts, target_interval=timedelta(hours=-1))


def test_reading_on_a_bucket_boundary_starts_its_own_bucket() -> None:
    """Regression: float rounding used to put a boundary reading in the bucket before it.

    Found by test_each_bucket_holds_exactly_the_readings_in_its_window. The
    bucket was labelled 23:59:59.999875, so it ended just *before* the reading.
    """
    midnight = datetime(2000, 1, 1, tzinfo=UTC)
    result = downsample(
        [DataPoint(timestamp=midnight, value=VALUE_10)], target_interval=timedelta(microseconds=125)
    )
    assert [bucket.timestamp for bucket in result] == [midnight]


def test_bucket_before_year_one_is_refused_with_invalid_window_error() -> None:
    """Regression: a bucket starting before year 1 used to crash with OverflowError.

    Found by test_downsampling_keeps_every_reading_exactly_once. Buckets line up
    with 1970-01-01, so this reading's bucket would start just before
    0001-01-01, which a datetime can't hold.
    """
    first_moment = datetime(1, 1, 1, tzinfo=UTC)
    with pytest.raises(InvalidWindowError, match="before year 1"):
        downsample(
            [DataPoint(timestamp=first_moment, value=VALUE_10)],
            target_interval=timedelta(seconds=1, microseconds=1),
        )
