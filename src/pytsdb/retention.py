"""Automatic expiry of old data points.

Think about newspapers.  You might keep today's and last week's, but
eventually you throw out the really old ones to save space.  A
*retention policy* does the same thing for data points -- it removes
anything older than a certain number of days.
"""

from datetime import UTC, datetime, timedelta

from pytsdb.datapoint import DataPoint
from pytsdb.errors import InvalidRetentionError


class RetentionPolicy:
    """A "spring cleaning" rule for old data.

    Just like throwing out newspapers once they're more than a week old,
    this rule quietly removes any data point older than ``max_age`` so your
    database doesn't fill up with ancient readings.

    Attributes:
        max_age: How long to keep data (e.g. 30 days).

    """

    def __init__(self, max_age: timedelta) -> None:
        """Create a retention policy.

        Args:
            max_age: The maximum age of data to keep.

        Raises:
            InvalidRetentionError: If *max_age* is zero or negative.

        """
        if max_age.total_seconds() <= 0:
            msg = "Retention period must be a positive duration"
            raise InvalidRetentionError(msg)
        self.max_age: timedelta = max_age

    def apply(
        self,
        points: list[DataPoint],
        now: datetime | None = None,
    ) -> list[DataPoint]:
        """Return only the points that are young enough to keep.

        Like going through your newspaper pile and keeping only the
        ones from the past week.

        Args:
            points: Data points to filter.
            now: The reference "current time."  Defaults to UTC now.

        Returns:
            A new list with only the non-expired points.

        """
        if now is None:
            now = datetime.now(tz=UTC)
        cutoff = now - self.max_age
        return [p for p in points if p.timestamp >= cutoff]

    def to_dict(self) -> dict[str, object]:
        """Serialize this policy to a plain dictionary.

        Returns:
            A dict with ``max_age_seconds``.

        """
        return {"max_age_seconds": self.max_age.total_seconds()}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RetentionPolicy:
        """Deserialize a retention policy from a plain dictionary.

        Args:
            data: A dict previously produced by :meth:`to_dict`.

        Returns:
            A new ``RetentionPolicy`` instance.

        """
        raw_seconds = data["max_age_seconds"]
        if not isinstance(raw_seconds, (int, float)):
            msg = "max_age_seconds must be numeric"
            raise TypeError(msg)
        return cls(max_age=timedelta(seconds=float(raw_seconds)))
