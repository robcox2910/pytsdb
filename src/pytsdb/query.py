"""Time-range queries and tag filtering.

Imagine a librarian helping you find books.  You might say:
  "Show me everything from *June* about *fantasy*."

That's exactly what queries do -- they narrow down data points
by **when** they happened and **what tags** they have.
"""

import bisect
from datetime import datetime

from pytsdb.datapoint import DataPoint


def query_range(
    points: list[DataPoint],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[DataPoint]:
    """Return points whose timestamps fall within [start, end].

    Uses binary search for speed -- like opening a phone book to the
    right letter instead of reading every page.

    Args:
        points: A **sorted** list of data points.
        start: Include points at or after this time (``None`` = no lower bound).
        end: Include points at or before this time (``None`` = no upper bound).

    Returns:
        A list of matching data points in chronological order.

    """
    if not points:
        return []

    lo = bisect.bisect_left(points, start, key=lambda p: p.timestamp) if start is not None else 0

    if end is not None:
        hi = bisect.bisect_right(points, end, key=lambda p: p.timestamp)
    else:
        hi = len(points)

    return points[lo:hi]


def filter_by_tags(
    points: list[DataPoint],
    tags: dict[str, str],
) -> list[DataPoint]:
    """Keep only points whose tags contain all specified key-value pairs.

    Like filtering your sticker collection: "show me only the blue,
    shiny ones."

    Args:
        points: Data points to filter.
        tags: Tag key-value pairs that must all match.

    Returns:
        A list of matching data points.

    """
    return [p for p in points if p.matches_tags(tags)]


def query(
    points: list[DataPoint],
    start: datetime | None = None,
    end: datetime | None = None,
    tags: dict[str, str] | None = None,
) -> list[DataPoint]:
    """Combine time-range and tag filtering in one call.

    A convenience function so you can say "give me kitchen-sensor
    readings from Tuesday to Thursday" in a single line.

    Args:
        points: A **sorted** list of data points.
        start: Lower time bound (inclusive).  ``None`` = no lower bound.
        end: Upper time bound (inclusive).  ``None`` = no upper bound.
        tags: Tag filters.  ``None`` = no tag filtering.

    Returns:
        A list of matching data points in chronological order.

    """
    result = query_range(points, start, end)
    if tags:
        result = filter_by_tags(result, tags)
    return result
