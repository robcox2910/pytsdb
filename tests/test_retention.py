"""Tests for retention policies."""

from datetime import UTC, datetime, timedelta

import pytest

from pytsdb.datapoint import DataPoint
from pytsdb.errors import InvalidRetentionError
from pytsdb.retention import RetentionPolicy

YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
DAY_1 = 1
HOUR_10 = 10
SEVEN_DAYS = timedelta(days=7)
ONE_DAY = timedelta(days=1)
VALUE_A = 10.0
VALUE_B = 20.0
VALUE_C = 30.0
MAX_AGE_SECONDS = 604800.0  # 7 days


def _ts(day: int, hour: int = HOUR_10) -> datetime:
    """Create a UTC timestamp in July 2024."""
    return datetime(YEAR_2024, MONTH_JULY, day, hour, 0, tzinfo=UTC)


class TestRetentionPolicy:
    """Test the RetentionPolicy class."""

    def test_keeps_recent_data(self) -> None:
        """Points within the retention window should be kept."""
        policy = RetentionPolicy(max_age=SEVEN_DAYS)
        now = _ts(10)
        points = [
            DataPoint(timestamp=_ts(5), value=VALUE_A),
            DataPoint(timestamp=_ts(8), value=VALUE_B),
            DataPoint(timestamp=_ts(10), value=VALUE_C),
        ]
        result = policy.apply(points, now=now)
        assert len(result) == 3  # noqa: PLR2004

    def test_removes_old_data(self) -> None:
        """Points older than max_age should be removed."""
        expected_kept = 2
        policy = RetentionPolicy(max_age=SEVEN_DAYS)
        now = _ts(10)
        points = [
            DataPoint(timestamp=_ts(DAY_1), value=VALUE_A),
            DataPoint(timestamp=_ts(8), value=VALUE_B),
            DataPoint(timestamp=_ts(10), value=VALUE_C),
        ]
        result = policy.apply(points, now=now)
        assert len(result) == expected_kept
        assert result[0].value == VALUE_B

    def test_invalid_zero_raises(self) -> None:
        """Zero max_age should raise InvalidRetentionError."""
        with pytest.raises(InvalidRetentionError):
            RetentionPolicy(max_age=timedelta(0))

    def test_invalid_negative_raises(self) -> None:
        """Negative max_age should raise InvalidRetentionError."""
        with pytest.raises(InvalidRetentionError):
            RetentionPolicy(max_age=timedelta(days=-1))


class TestRetentionSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        """Serializing and deserializing should preserve the max_age."""
        policy = RetentionPolicy(max_age=SEVEN_DAYS)
        data = policy.to_dict()
        assert data["max_age_seconds"] == MAX_AGE_SECONDS
        restored = RetentionPolicy.from_dict(data)
        assert restored.max_age == SEVEN_DAYS

    def test_from_dict_bad_type(self) -> None:
        """Raise TypeError if max_age_seconds is not numeric."""
        with pytest.raises(TypeError, match="max_age_seconds"):
            RetentionPolicy.from_dict({"max_age_seconds": "bad"})
