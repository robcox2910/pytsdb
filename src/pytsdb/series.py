"""A named collection of ordered data points.

Picture a lab notebook where you record temperature every hour.
The notebook is the *TimeSeries*, and each row is a *DataPoint*.
The readings are always in order, oldest first, so you can quickly
flip to any date.
"""

import bisect
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime

from pytsdb.datapoint import DataPoint
from pytsdb.errors import EmptySeriesError


def _copy(point: DataPoint) -> DataPoint:
    """Return a fresh copy of *point*, with its own copy of the tags.

    A frozen point can't be changed, but its tags dict can. The series
    keeps its points to itself and hands out copies, so scribbling on the
    tags of a point you were given can never change what's stored.
    """
    return replace(point)  # DataPoint.__post_init__ copies the tags


def _when(point: DataPoint) -> datetime:
    """Return when *point* was taken: the only thing a series sorts by."""
    return point.timestamp


class TimeSeries:
    """An ordered collection of :class:`DataPoint` objects for one metric.

    Points are kept sorted by timestamp so range look-ups are fast --
    like keeping your lab notebook pages in date order.

    Attributes:
        name: A human-readable label (e.g. ``"temperature"``).

    """

    def __init__(self, name: str) -> None:
        """Create a new, empty time series.

        Args:
            name: The name of this metric (e.g. ``"cpu_usage"``).

        """
        self.name: str = name
        self._points: list[DataPoint] = []

    # ------------------------------------------------------------------
    # Size helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of data points in this series."""
        return len(self._points)

    def __iter__(self) -> Iterator[DataPoint]:
        """Iterate over copies of all data points in chronological order."""
        return (_copy(point) for point in self._points)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, point: DataPoint) -> None:
        """Insert a copy of a data point, keeping chronological order.

        Uses binary search (like flipping to the right page in a sorted
        notebook) so it stays fast even with millions of points. Points
        are ordered by timestamp only: readings taken at the same moment
        stay in the order they were added.

        Args:
            point: The data point to add.

        """
        bisect.insort(self._points, _copy(point), key=_when)

    def add_value(
        self,
        value: float,
        timestamp: datetime | None = None,
        tags: dict[str, str] | None = None,
    ) -> DataPoint:
        """Create and insert a data point in one step.

        A convenience helper so callers don't need to import
        :class:`DataPoint` directly.

        Args:
            value: The numeric reading.
            timestamp: When the reading was taken.  Defaults to *now*.
            tags: Optional key-value labels.

        Returns:
            The newly created :class:`DataPoint`.

        """
        if timestamp is None:
            point = DataPoint(value=value, tags=tags or {})
        else:
            point = DataPoint(timestamp=timestamp, value=value, tags=tags or {})
        self.add(point)
        return point

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @property
    def first(self) -> DataPoint:
        """Return the oldest data point.

        Raises:
            EmptySeriesError: If the series has no points.

        """
        if not self._points:
            msg = f"Series '{self.name}' is empty"
            raise EmptySeriesError(msg)
        return _copy(self._points[0])

    @property
    def last(self) -> DataPoint:
        """Return the newest data point.

        Raises:
            EmptySeriesError: If the series has no points.

        """
        if not self._points:
            msg = f"Series '{self.name}' is empty"
            raise EmptySeriesError(msg)
        return _copy(self._points[-1])

    @property
    def points(self) -> list[DataPoint]:
        """Return copies of all points (chronological order)."""
        return [_copy(point) for point in self._points]

    def clear(self) -> None:
        """Remove all data points from this series."""
        self._points.clear()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Serialize this series to a plain dictionary.

        Returns:
            A dict with ``name`` and ``points`` (list of point dicts).

        """
        return {
            "name": self.name,
            "points": [p.to_dict() for p in self._points],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TimeSeries:
        """Deserialize a series from a plain dictionary.

        Args:
            data: A dict previously produced by :meth:`to_dict`.

        Returns:
            A new ``TimeSeries`` instance.

        """
        raw_name = data["name"]
        if not isinstance(raw_name, str):
            msg = "name must be a string"
            raise TypeError(msg)
        series = cls(name=raw_name)
        raw_points = data.get("points", [])
        if not isinstance(raw_points, list):
            msg = "points must be a list"
            raise TypeError(msg)
        for raw_pt in raw_points:  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(raw_pt, dict):
                msg = "each point must be a dict"
                raise TypeError(msg)
            pt_data: dict[str, object] = {str(k): v for k, v in raw_pt.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            series.add(DataPoint.from_dict(pt_data))
        return series
