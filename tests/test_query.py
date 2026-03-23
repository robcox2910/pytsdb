"""Tests for query functions."""

from datetime import UTC, datetime

from pytsdb.datapoint import DataPoint
from pytsdb.query import filter_by_tags, query, query_range

TEMP_HIGH = 75.0
TEMP_MID = 72.5
TEMP_LOW = 68.0
YEAR_2024 = 2024
MONTH_JULY = 7
DAY_4 = 4
HOUR_8 = 8
HOUR_10 = 10
HOUR_12 = 12
HOUR_14 = 14
HOUR_16 = 16


def _ts(hour: int) -> datetime:
    """Create a UTC timestamp on July 4, 2024 at the given hour."""
    return datetime(YEAR_2024, MONTH_JULY, DAY_4, hour, 0, tzinfo=UTC)


def _sample_points() -> list[DataPoint]:
    """Create a sorted list of sample data points."""
    return [
        DataPoint(timestamp=_ts(HOUR_8), value=TEMP_LOW, tags={"sensor": "kitchen"}),
        DataPoint(timestamp=_ts(HOUR_10), value=TEMP_MID, tags={"sensor": "bedroom"}),
        DataPoint(timestamp=_ts(HOUR_12), value=TEMP_HIGH, tags={"sensor": "kitchen"}),
        DataPoint(timestamp=_ts(HOUR_14), value=TEMP_MID, tags={"sensor": "bedroom"}),
        DataPoint(timestamp=_ts(HOUR_16), value=TEMP_LOW, tags={"sensor": "kitchen"}),
    ]


class TestQueryRange:
    """Test time-range queries."""

    def test_full_range(self) -> None:
        """No bounds should return all points."""
        pts = _sample_points()
        assert len(query_range(pts)) == len(pts)

    def test_start_only(self) -> None:
        """Start bound should exclude earlier points."""
        pts = _sample_points()
        result = query_range(pts, start=_ts(HOUR_12))
        assert len(result) == 3  # noqa: PLR2004
        assert result[0].timestamp == _ts(HOUR_12)

    def test_end_only(self) -> None:
        """End bound should exclude later points."""
        pts = _sample_points()
        result = query_range(pts, end=_ts(HOUR_12))
        assert len(result) == 3  # noqa: PLR2004
        assert result[-1].timestamp == _ts(HOUR_12)

    def test_start_and_end(self) -> None:
        """Both bounds should narrow the range."""
        pts = _sample_points()
        result = query_range(pts, start=_ts(HOUR_10), end=_ts(HOUR_14))
        assert len(result) == 3  # noqa: PLR2004

    def test_empty_list(self) -> None:
        """Querying an empty list should return an empty list."""
        assert query_range([]) == []

    def test_no_matches(self) -> None:
        """Return empty when range excludes all points."""
        pts = _sample_points()
        very_early = datetime(YEAR_2024, 1, 1, tzinfo=UTC)
        very_early_end = datetime(YEAR_2024, 1, 2, tzinfo=UTC)
        result = query_range(pts, start=very_early, end=very_early_end)
        assert result == []


class TestFilterByTags:
    """Test tag-based filtering."""

    def test_filter_single_tag(self) -> None:
        """Filter by one tag key-value pair."""
        pts = _sample_points()
        result = filter_by_tags(pts, {"sensor": "kitchen"})
        assert len(result) == 3  # noqa: PLR2004

    def test_filter_no_match(self) -> None:
        """Return empty when no points match."""
        pts = _sample_points()
        result = filter_by_tags(pts, {"sensor": "garage"})
        assert result == []

    def test_empty_tags_returns_all(self) -> None:
        """An empty tag filter should return all points."""
        pts = _sample_points()
        result = filter_by_tags(pts, {})
        assert len(result) == len(pts)


class TestCombinedQuery:
    """Test the combined query function."""

    def test_time_and_tags(self) -> None:
        """Combine time range and tag filter."""
        pts = _sample_points()
        result = query(pts, start=_ts(HOUR_10), end=_ts(HOUR_14), tags={"sensor": "kitchen"})
        assert len(result) == 1
        assert result[0].timestamp == _ts(HOUR_12)

    def test_no_tags_filter(self) -> None:
        """Passing tags=None should skip tag filtering."""
        pts = _sample_points()
        result = query(pts, start=_ts(HOUR_10), end=_ts(HOUR_14))
        assert len(result) == 3  # noqa: PLR2004
