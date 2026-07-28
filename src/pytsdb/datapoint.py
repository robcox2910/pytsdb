"""A single timestamped measurement.

Imagine you're a scientist checking a thermometer.  You jot down:
  - **When** you looked (the timestamp)
  - **What** the reading was (the value)
  - **Where / extra info** (the tags, like "room=kitchen")

A ``DataPoint`` is exactly that note.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True, order=True)
class DataPoint:
    """A single timestamped value with optional tags.

    Attributes:
        timestamp: When the measurement was taken (UTC).
        value: The numeric reading.
        tags: Optional key-value labels (e.g. ``{"sensor": "kitchen"}``).

    Example:
        >>> from datetime import datetime, timezone
        >>> dp = DataPoint(
        ...     timestamp=datetime(2024, 7, 4, 14, 0, tzinfo=timezone.utc),
        ...     value=72.5,
        ...     tags={"sensor": "kitchen"},
        ... )
        >>> dp.value
        72.5

    """

    timestamp: datetime = field(default_factory=_utc_now)
    value: float = 0.0
    tags: dict[str, str] = field(default_factory=lambda: {}, compare=False)

    def __post_init__(self) -> None:
        """Tidy up the note right after it's written.

        Two bits of housekeeping happen here:

        * We make sure the timestamp knows its timezone.  A bare
          ``datetime(2024, 1, 1)`` has no timezone attached, which would
          cause confusing crashes later when we compare times, so we
          catch it early with a friendly message.
        * We take our *own* copy of the tags.  Otherwise, if you kept the
          dict you passed in and edited it, this "written in pen" point
          would silently change too -- which it must never do.
        """
        if self.timestamp.tzinfo is None or self.timestamp.tzinfo.utcoffset(self.timestamp) is None:
            msg = (
                "timestamp must be timezone-aware -- add a timezone like "
                "datetime(2024, 1, 1, tzinfo=timezone.utc). A naive "
                "datetime (no timezone) was given."
            )
            raise ValueError(msg)
        object.__setattr__(self, "tags", dict(self.tags))

    def matches_tags(self, filter_tags: dict[str, str]) -> bool:
        """Check whether this point's tags contain all *filter_tags*.

        Like checking if a label on a jar includes all the words you're
        looking for.

        Args:
            filter_tags: Tag key-value pairs that must all be present.

        Returns:
            ``True`` if every key-value pair in *filter_tags* appears in
            this point's tags.

        """
        return all(self.tags.get(k) == v for k, v in filter_tags.items())

    def to_dict(self) -> dict[str, object]:
        """Serialize this data point to a plain dictionary.

        Returns:
            A dict with ``timestamp`` (ISO string), ``value``, and ``tags``.

        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DataPoint:
        """Deserialize a data point from a plain dictionary.

        Args:
            data: A dict previously produced by :meth:`to_dict`.

        Returns:
            A new ``DataPoint`` instance.

        """
        raw_ts = data["timestamp"]
        if not isinstance(raw_ts, str):
            msg = "timestamp must be an ISO-format string"
            raise TypeError(msg)
        ts = datetime.fromisoformat(raw_ts)
        raw_value = data["value"]
        if not isinstance(raw_value, (int, float)):
            msg = "value must be numeric"
            raise TypeError(msg)
        raw_tags = data.get("tags", {})
        if not isinstance(raw_tags, dict):
            msg = "tags must be a dict"
            raise TypeError(msg)
        tags: dict[str, str] = {str(k): str(v) for k, v in raw_tags.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        return cls(timestamp=ts, value=float(raw_value), tags=tags)
