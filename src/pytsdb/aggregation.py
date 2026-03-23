"""Windowed aggregation functions.

Suppose you recorded the temperature every minute for a whole day.
That's 1,440 readings!  Aggregation lets you *summarise* them:

  - "What was the **average** temperature each hour?"
  - "What was the **highest** reading today?"

You pick a *window* (like one hour) and a *function* (like average),
and the aggregator crunches the numbers for you.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from enum import Enum

from pytsdb.datapoint import DataPoint
from pytsdb.errors import EmptySeriesError, InvalidWindowError


class AggFunc(Enum):
    """Supported aggregation functions.

    Each value names a way to summarise a group of numbers.
    """

    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"


def _bucket_key(timestamp: datetime, window: timedelta) -> datetime:
    """Return the start of the time bucket that *timestamp* falls into.

    Args:
        timestamp: The point in time to bucket.
        window: The size of each bucket.

    Returns:
        A UTC datetime representing the start of the bucket.

    """
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    total_seconds = (timestamp - epoch).total_seconds()
    window_seconds = window.total_seconds()
    bucket_start = int(total_seconds // window_seconds) * window_seconds
    return epoch + timedelta(seconds=bucket_start)


def aggregate(
    points: list[DataPoint],
    window: timedelta,
    func: AggFunc = AggFunc.AVG,
) -> list[DataPoint]:
    """Group points into time windows and compute a summary value.

    Think of it like sorting your marbles into jars by colour
    and then counting how many are in each jar.

    Args:
        points: Sorted data points to aggregate.
        window: The size of each time bucket (e.g. ``timedelta(hours=1)``).
        func: Which summary to compute (avg, min, max, sum, count).

    Returns:
        One :class:`~pytsdb.datapoint.DataPoint` per bucket, timestamped
        at the bucket start, with the aggregated value.

    Raises:
        EmptySeriesError: If *points* is empty.
        InvalidWindowError: If *window* is zero or negative.

    """
    if not points:
        msg = "Cannot aggregate an empty list of points"
        raise EmptySeriesError(msg)

    if window.total_seconds() <= 0:
        msg = "Window must be a positive duration"
        raise InvalidWindowError(msg)

    # Group points by bucket
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for point in points:
        key = _bucket_key(point.timestamp, window)
        buckets[key].append(point.value)

    # Compute aggregate per bucket
    result: list[DataPoint] = []
    for bucket_ts in sorted(buckets):
        values = buckets[bucket_ts]
        agg_value = _compute(values, func)
        result.append(DataPoint(timestamp=bucket_ts, value=agg_value))

    return result


def _compute(values: list[float], func: AggFunc) -> float:
    """Apply an aggregation function to a list of numbers.

    Args:
        values: Non-empty list of floats.
        func: Which aggregation to apply.

    Returns:
        The aggregated result.

    """
    if func is AggFunc.AVG:
        return sum(values) / len(values)
    if func is AggFunc.MIN:
        return min(values)
    if func is AggFunc.MAX:
        return max(values)
    if func is AggFunc.SUM:
        return sum(values)
    # COUNT
    return float(len(values))
