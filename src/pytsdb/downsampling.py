"""Resolution reduction for time-series data.

Imagine you have a diary where you wrote a sentence every minute for
a whole year.  That's a LOT of pages!  Downsampling is like writing a
*summary* -- one sentence per hour, or per day -- so you can see the
big picture without drowning in detail.

Under the hood, downsampling is just aggregation with a specific
window size, but it's such a common operation that it deserves its
own module.
"""

from datetime import timedelta

from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.datapoint import DataPoint
from pytsdb.errors import InvalidWindowError


def downsample(
    points: list[DataPoint],
    target_interval: timedelta,
    func: AggFunc = AggFunc.AVG,
) -> list[DataPoint]:
    """Reduce the resolution of a data-point list.

    For example, turn per-minute readings into per-hour averages.

    Args:
        points: Sorted data points at the original resolution.
        target_interval: The desired bucket size
            (e.g. ``timedelta(hours=1)``).
        func: How to combine values within each bucket.

    Returns:
        A new list of data points at the lower resolution.

    Raises:
        InvalidWindowError: If *target_interval* is zero or negative.

    """
    if target_interval.total_seconds() <= 0:
        msg = "Target interval must be a positive duration"
        raise InvalidWindowError(msg)

    if not points:
        return []

    return aggregate(points, window=target_interval, func=func)
