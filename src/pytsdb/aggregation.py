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

    Raises:
        InvalidWindowError: If the bucket would start before year 1.

    """
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    # Count whole windows with timedelta arithmetic, which is exact to the
    # microsecond. Going through float seconds rounded, and could label a
    # bucket a hair *after* its first reading -- or put a reading that sits
    # exactly on a boundary into the bucket before it.
    windows_since_epoch = (timestamp - epoch) // window
    try:
        return epoch + windows_since_epoch * window
    except OverflowError:
        # Buckets line up with 1970-01-01, so a reading in the first window
        # of the calendar can need a bucket starting before 0001-01-01, the
        # earliest moment a datetime can hold.
        msg = (
            f"A {window} window puts the bucket for {timestamp.isoformat()} "
            "before year 1, which a datetime can't hold -- use a smaller window"
        )
        raise InvalidWindowError(msg) from None


def aggregate(
    points: list[DataPoint],
    window: timedelta,
    func: AggFunc = AggFunc.AVG,
) -> list[DataPoint]:
    """Group points into time windows and compute a summary value.

    Think of it like sorting your marbles into jars by colour
    and then counting how many are in each jar.

    Buckets line up with midnight on 1 January 1970, counting whole
    windows forwards or backwards from there.

    Args:
        points: Sorted data points to aggregate.
        window: The size of each time bucket (e.g. ``timedelta(hours=1)``).
        func: Which summary to compute (avg, min, max, sum, count).

    Returns:
        One :class:`~pytsdb.datapoint.DataPoint` per bucket, timestamped
        at the bucket start, with the aggregated value.

    Raises:
        EmptySeriesError: If *points* is empty.
        InvalidWindowError: If *window* is zero or negative, or if a
            point's bucket would start before year 1 (only possible for a
            point less than one window after 0001-01-01 00:00).

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
