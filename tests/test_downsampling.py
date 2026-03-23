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
