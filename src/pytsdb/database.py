"""Container for multiple time series.

A ``TimeSeriesDB`` is like a filing cabinet.  Each drawer is a
*TimeSeries* with its own name.  You can open a drawer, add readings,
look things up, or throw out a whole drawer you don't need any more.
"""

from datetime import datetime, timedelta

from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.datapoint import DataPoint
from pytsdb.downsampling import downsample
from pytsdb.errors import DuplicateSeriesError, SeriesNotFoundError
from pytsdb.query import query
from pytsdb.retention import RetentionPolicy
from pytsdb.series import TimeSeries


class TimeSeriesDB:
    """A filing cabinet that holds many named time series.

    Each drawer is a :class:`~pytsdb.series.TimeSeries` with its own name.
    You can open a drawer to add readings, look things up, or throw out a
    whole drawer you don't need any more. Everything lives in memory.

    Example:
        >>> db = TimeSeriesDB()
        >>> db.create_series("temperature")
        >>> db.add_point("temperature", value=72.5)

    """

    def __init__(self) -> None:
        """Create a new, empty database."""
        self._series: dict[str, TimeSeries] = {}
        self._retention: dict[str, RetentionPolicy] = {}

    # ------------------------------------------------------------------
    # Series CRUD
    # ------------------------------------------------------------------

    def create_series(self, name: str) -> TimeSeries:
        """Create a new, empty time series.

        Args:
            name: A unique name for the series.

        Returns:
            The newly created :class:`~pytsdb.series.TimeSeries`.

        Raises:
            DuplicateSeriesError: If *name* is already in use.

        """
        if name in self._series:
            msg = f"Series '{name}' already exists"
            raise DuplicateSeriesError(msg)
        series = TimeSeries(name)
        self._series[name] = series
        return series

    def get_series(self, name: str) -> TimeSeries:
        """Retrieve a series by name.

        Args:
            name: The series name.

        Returns:
            The matching :class:`~pytsdb.series.TimeSeries`.

        Raises:
            SeriesNotFoundError: If no series with *name* exists.

        """
        try:
            return self._series[name]
        except KeyError:
            msg = f"Series '{name}' not found"
            raise SeriesNotFoundError(msg) from None

    def delete_series(self, name: str) -> None:
        """Remove a series entirely.

        Args:
            name: The series to delete.

        Raises:
            SeriesNotFoundError: If no series with *name* exists.

        """
        try:
            del self._series[name]
        except KeyError:
            msg = f"Series '{name}' not found"
            raise SeriesNotFoundError(msg) from None
        self._retention.pop(name, None)

    def list_series(self) -> list[str]:
        """Return the names of all series, sorted alphabetically."""
        return sorted(self._series)

    @property
    def series_count(self) -> int:
        """Return the number of series in the database."""
        return len(self._series)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def add_point(
        self,
        series_name: str,
        value: float,
        timestamp: datetime | None = None,
        tags: dict[str, str] | None = None,
    ) -> DataPoint:
        """Add a single data point to an existing series.

        Args:
            series_name: Which series to add to.
            value: The numeric reading.
            timestamp: When the reading was taken (defaults to now).
            tags: Optional key-value labels.

        Returns:
            The newly created :class:`~pytsdb.datapoint.DataPoint`.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        series = self.get_series(series_name)
        return series.add_value(value, timestamp=timestamp, tags=tags)

    def query(
        self,
        series_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
        tags: dict[str, str] | None = None,
    ) -> list[DataPoint]:
        """Query a series by time range and/or tags.

        Args:
            series_name: Which series to query.
            start: Lower time bound (inclusive).
            end: Upper time bound (inclusive).
            tags: Tag filters.

        Returns:
            Matching data points in chronological order.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        series = self.get_series(series_name)
        return query(series.points, start=start, end=end, tags=tags)

    def aggregate(
        self,
        series_name: str,
        window: timedelta,
        func: AggFunc = AggFunc.AVG,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DataPoint]:
        """Aggregate a series over fixed time windows.

        Args:
            series_name: Which series to aggregate.
            window: Bucket size (e.g. 1 hour).
            func: Aggregation function.
            start: Optional lower time bound for pre-filtering.
            end: Optional upper time bound for pre-filtering.

        Returns:
            One data point per bucket with the aggregated value.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        points = self.query(series_name, start=start, end=end)
        if not points:
            return []
        return aggregate(points, window=window, func=func)

    def downsample(
        self,
        series_name: str,
        target_interval: timedelta,
        func: AggFunc = AggFunc.AVG,
    ) -> list[DataPoint]:
        """Downsample a series to a coarser resolution.

        Args:
            series_name: Which series to downsample.
            target_interval: Desired bucket size.
            func: How to combine values within each bucket.

        Returns:
            A new list of data points at the lower resolution.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        series = self.get_series(series_name)
        return downsample(series.points, target_interval=target_interval, func=func)

    # ------------------------------------------------------------------
    # Rate of change
    # ------------------------------------------------------------------

    def rate_of_change(self, series_name: str) -> list[DataPoint]:
        """Compute the rate of change between consecutive points.

        The rate of change tells you how fast a value is changing --
        like checking your speedometer (how fast distance changes over
        time).

        Args:
            series_name: Which series to analyse.

        Returns:
            A list of data points where each value is the rate
            (units per second) between consecutive original points.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        series = self.get_series(series_name)
        pts = series.points
        result: list[DataPoint] = []
        for i in range(1, len(pts)):
            dt = (pts[i].timestamp - pts[i - 1].timestamp).total_seconds()
            if dt == 0:
                continue
            rate = (pts[i].value - pts[i - 1].value) / dt
            result.append(DataPoint(timestamp=pts[i].timestamp, value=rate))
        return result

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def set_retention(self, series_name: str, max_age: timedelta) -> None:
        """Set a retention policy on a series.

        Args:
            series_name: Which series to apply the policy to.
            max_age: How long to keep data.

        Raises:
            SeriesNotFoundError: If the series doesn't exist.

        """
        self.get_series(series_name)  # validate existence
        self._retention[series_name] = RetentionPolicy(max_age=max_age)

    def apply_retention(self, now: datetime | None = None) -> int:
        """Apply all retention policies, removing expired points.

        Args:
            now: The reference "current time."  Defaults to UTC now.

        Returns:
            Total number of points removed across all series.

        """
        removed = 0
        for name, policy in self._retention.items():
            series = self._series[name]
            before = len(series)
            kept = policy.apply(series.points, now=now)
            series.clear()
            for p in kept:
                series.add(p)
            removed += before - len(series)
        return removed

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """Serialize the entire database to a plain dictionary.

        Returns:
            A dict with ``series`` and ``retention`` keys.

        """
        retention_data: dict[str, object] = {}
        for name, policy in self._retention.items():
            retention_data[name] = policy.to_dict()
        return {
            "series": {name: s.to_dict() for name, s in self._series.items()},
            "retention": retention_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TimeSeriesDB:
        """Deserialize a database from a plain dictionary.

        Args:
            data: A dict previously produced by :meth:`to_dict`.

        Returns:
            A new ``TimeSeriesDB`` instance.

        """
        db = cls()
        raw_series = data.get("series", {})
        if not isinstance(raw_series, dict):
            msg = "series must be a dict"
            raise TypeError(msg)
        for raw_s in raw_series.values():  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(raw_s, dict):
                msg = "each series must be a dict"
                raise TypeError(msg)
            s_data: dict[str, object] = {str(k): v for k, v in raw_s.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            series = TimeSeries.from_dict(s_data)
            db._series[series.name] = series

        raw_retention = data.get("retention", {})
        if not isinstance(raw_retention, dict):
            msg = "retention must be a dict"
            raise TypeError(msg)
        for name, raw_policy in raw_retention.items():  # pyright: ignore[reportUnknownVariableType]
            if not isinstance(raw_policy, dict):
                msg = "each retention policy must be a dict"
                raise TypeError(msg)
            p_data: dict[str, object] = {str(k): v for k, v in raw_policy.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            db._retention[str(name)] = RetentionPolicy.from_dict(p_data)  # pyright: ignore[reportUnknownArgumentType]

        return db
