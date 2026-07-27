"""Tests for the DataPoint dataclass."""

from datetime import UTC, datetime

import pytest

from pytsdb.datapoint import DataPoint

TEMP_KITCHEN = 72.5
TEMP_BEDROOM = 68.0
JULY_4_HOUR = 14
YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4


def _make_ts(hour: int = JULY_4_HOUR) -> datetime:
    """Create a UTC timestamp on July 4, 2024."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, 0, tzinfo=UTC)


class TestDataPointCreation:
    """Test creating DataPoint instances."""

    def test_create_with_all_fields(self) -> None:
        """Create a data point with explicit timestamp, value, and tags."""
        ts = _make_ts()
        dp = DataPoint(timestamp=ts, value=TEMP_KITCHEN, tags={"sensor": "kitchen"})
        assert dp.timestamp == ts
        assert dp.value == TEMP_KITCHEN
        assert dp.tags == {"sensor": "kitchen"}

    def test_default_timestamp_is_utc(self) -> None:
        """Default timestamp should be UTC."""
        dp = DataPoint(value=TEMP_KITCHEN)
        assert dp.timestamp.tzinfo is not None

    def test_default_value_is_zero(self) -> None:
        """Default value should be 0.0."""
        dp = DataPoint()
        assert dp.value == 0.0

    def test_default_tags_are_empty(self) -> None:
        """Default tags should be an empty dict."""
        dp = DataPoint(value=TEMP_KITCHEN)
        assert dp.tags == {}

    def test_frozen(self) -> None:
        """DataPoint should be immutable."""
        dp = DataPoint(value=TEMP_KITCHEN)
        with pytest.raises(AttributeError):
            dp.value = 99.0  # type: ignore[misc]

    def test_tags_are_copied(self) -> None:
        """Editing the caller's dict must not change a frozen point."""
        labels = {"sensor": "kitchen"}
        dp = DataPoint(value=TEMP_KITCHEN, tags=labels)
        labels["sensor"] = "garage"
        labels["floor"] = "2"
        assert dp.tags == {"sensor": "kitchen"}

    def test_naive_timestamp_rejected(self) -> None:
        """A timestamp without a timezone should raise a clear error."""
        with pytest.raises(ValueError, match="timezone-aware"):
            DataPoint(timestamp=datetime(YEAR_2024, MONTH_JULY, DAY_4))  # noqa: DTZ001


class TestDataPointOrdering:
    """Test that data points sort by timestamp."""

    def test_sort_by_timestamp(self) -> None:
        """Earlier timestamps sort before later ones."""
        early = DataPoint(timestamp=_make_ts(10), value=TEMP_KITCHEN)
        late = DataPoint(timestamp=_make_ts(JULY_4_HOUR), value=TEMP_BEDROOM)
        assert early < late

    def test_equal_timestamps_sort_by_value(self) -> None:
        """Points with the same timestamp sort by value."""
        ts = _make_ts()
        low = DataPoint(timestamp=ts, value=TEMP_BEDROOM)
        high = DataPoint(timestamp=ts, value=TEMP_KITCHEN)
        assert low < high


class TestTagMatching:
    """Test the matches_tags filter method."""

    def test_matches_subset(self) -> None:
        """Point matches when it contains all filter tags."""
        dp = DataPoint(value=TEMP_KITCHEN, tags={"sensor": "kitchen", "floor": "1"})
        assert dp.matches_tags({"sensor": "kitchen"}) is True

    def test_no_match(self) -> None:
        """Point does not match when a tag value differs."""
        dp = DataPoint(value=TEMP_KITCHEN, tags={"sensor": "kitchen"})
        assert dp.matches_tags({"sensor": "bedroom"}) is False

    def test_empty_filter_always_matches(self) -> None:
        """An empty filter matches every point."""
        dp = DataPoint(value=TEMP_KITCHEN, tags={"sensor": "kitchen"})
        assert dp.matches_tags({}) is True

    def test_missing_key_no_match(self) -> None:
        """Point does not match if it lacks a required tag key."""
        dp = DataPoint(value=TEMP_KITCHEN, tags={})
        assert dp.matches_tags({"sensor": "kitchen"}) is False


class TestDataPointSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_round_trip(self) -> None:
        """Serializing and deserializing should produce an equal point."""
        dp = DataPoint(timestamp=_make_ts(), value=TEMP_KITCHEN, tags={"sensor": "kitchen"})
        restored = DataPoint.from_dict(dp.to_dict())
        assert restored.timestamp == dp.timestamp
        assert restored.value == dp.value
        assert restored.tags == dp.tags

    def test_from_dict_bad_timestamp_type(self) -> None:
        """Raise TypeError if timestamp is not a string."""
        with pytest.raises(TypeError, match="timestamp"):
            DataPoint.from_dict({"timestamp": 123, "value": 1.0})

    def test_from_dict_bad_value_type(self) -> None:
        """Raise TypeError if value is not numeric."""
        with pytest.raises(TypeError, match="value"):
            DataPoint.from_dict({"timestamp": _make_ts().isoformat(), "value": "not a number"})

    def test_from_dict_bad_tags_type(self) -> None:
        """Raise TypeError if tags is not a dict."""
        with pytest.raises(TypeError, match="tags"):
            DataPoint.from_dict(
                {
                    "timestamp": _make_ts().isoformat(),
                    "value": 1.0,
                    "tags": "bad",
                }
            )
