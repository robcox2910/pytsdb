"""Strategies -- recipes for random readings, shared by the property tests.

A strategy tells Hypothesis how to invent one kind of input. Each one here
is a named function, named for what it makes, with a one-line docstring.
``tests/test_properties.py`` and ``tests/test_model.py`` both use them.
"""

from datetime import UTC, datetime, timedelta

from hypothesis import strategies as st


def _without_fold(moment: datetime) -> datetime:
    """Return ``moment`` with ``fold`` set back to 0."""
    return moment.replace(fold=0)


def timestamps() -> st.SearchStrategy[datetime]:
    """Make any moment from year 1 to year 9999, down to the microsecond, in UTC."""
    # DataPoint documents its timestamp as "When the measurement was taken (UTC)".
    # ``fold=1`` marks the second 1:30am on the night the clocks go back. UTC
    # never goes back, so there it means nothing, and isoformat() drops it.
    return st.datetimes(timezones=st.just(UTC)).map(_without_fold)


def readings() -> st.SearchStrategy[float]:
    """Make any reading at all: negative, zero, huge, tiny, infinite or NaN ("not a number")."""
    return st.floats()


def tag_sets() -> st.SearchStrategy[dict[str, str]]:
    """Make a few labels, like ``{"room": "kitchen"}``, or none at all."""
    return st.dictionaries(st.text(max_size=5), st.text(max_size=5), max_size=2)


def durations() -> st.SearchStrategy[timedelta]:
    """Make any positive length of time, from one microsecond upwards."""
    return st.timedeltas(min_value=timedelta(microseconds=1))
