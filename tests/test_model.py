"""Model check -- TimeSeriesDB must behave like a plain list of readings.

A property test checks one rule for many inputs. A *model check* goes
further: Hypothesis invents a random *story* -- make a series, add a
reading from last Tuesday, add one from 1850, ask for everything in June,
throw out old readings, delete the series -- and plays it on two things at
once:

- the real ``TimeSeriesDB``;
- a **model**: a dict of plain Python lists, one unsorted list of
  ``(timestamp, value, tags)`` per series, which we already trust.

After every step the two must agree. If they ever disagree, Hypothesis
shrinks the story to the shortest list of steps that still goes wrong.

The model is deliberately *not* a copy of ``TimeSeriesDB``'s code. It
never sorts anything as it goes and never uses binary search: it keeps
readings in the order they arrived and, when asked a question, simply
looks at every one. So when the two disagree, the database is the one to
suspect.

Retention ("throw out readings older than 30 days") normally reads the
real clock, which a model check must never do. Here every
``apply_retention`` call is handed a made-up "now", so the story can jump
across centuries in an instant.

See ``docs/property-testing.md`` for the walk-through.
"""

import unittest
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    MultipleResults,
    RuleBasedStateMachine,
    initialize,
    invariant,
    multiple,
    rule,
)

from pytsdb.database import TimeSeriesDB
from pytsdb.datapoint import DataPoint
from pytsdb.errors import DuplicateSeriesError, EmptySeriesError, SeriesNotFoundError
from tests.strategies import durations, readings, tag_sets, timestamps

# The very last moment a datetime can hold: just before midnight, 31 December 9999.
LAST_MOMENT = datetime.max.replace(tzinfo=UTC)

# A reading is (when, what value, which labels).
type Reading = tuple[datetime, float, dict[str, str]]


def early_morning_hours() -> st.SearchStrategy[datetime]:
    """Make one of the six o'clocks from midnight to 5am on 4 July 2024, so moments often match."""
    midnight = datetime(2024, 7, 4, tzinfo=UTC)
    return st.sampled_from([midnight + timedelta(hours=hour) for hour in range(6)])


def moments() -> st.SearchStrategy[datetime]:
    """Make a moment that's often an early-morning hour, and sometimes any moment at all."""
    # Two random moments down to the microsecond are almost never equal, so
    # two readings at the same moment would hardly ever come up.
    return st.one_of(early_morning_hours(), timestamps())


def whole_hours() -> st.SearchStrategy[timedelta]:
    """Make a length of time from 1 to 5 whole hours."""
    return st.builds(timedelta, hours=st.integers(min_value=1, max_value=5))


def lengths_of_time() -> st.SearchStrategy[timedelta]:
    """Make a length of time that's often whole hours, and sometimes any positive length."""
    return st.one_of(whole_hours(), durations())


def some_names() -> st.SearchStrategy[str]:
    """Pick one of three series names, so the same name comes up again and again."""
    # Any text works as a name (the save/load property tries all sorts), but
    # three names mean the story keeps coming back to the same series.
    return st.sampled_from(["temperature", "rain", ""])


def batches_of_readings() -> st.SearchStrategy[list[Reading]]:
    """Make one to five readings, in no particular order."""
    return st.lists(st.tuples(moments(), readings(), tag_sets()), min_size=1, max_size=5)


def as_readings(points: list[DataPoint]) -> list[Reading]:
    """Turn the database's data points into plain (timestamp, value, tags) tuples."""
    return [(p.timestamp, p.value, p.tags) for p in points]


def same_readings_in_time_order(got: list[Reading], expected: list[Reading]) -> bool:
    """Say whether ``got`` holds exactly the ``expected`` readings, oldest first."""
    oldest_first = [timestamp for timestamp, _, _ in got] == sorted(t for t, _, _ in expected)
    # ``repr`` tells 1 from 1.0, and lets a NaN reading match itself.
    same_pile = Counter(map(repr, got)) == Counter(map(repr, expected))
    return oldest_first and same_pile


# --- The machine: one story, played on the database and on plain lists -------


class TimeSeriesDBMachine(RuleBasedStateMachine):
    """Play random steps on a TimeSeriesDB and on a dict of unsorted lists side by side."""

    # Moments that readings were taken at. Two random moments almost never
    # match, so queries and retention also pick from here, to try asking
    # for readings that end *exactly* on one, or are *exactly* max_age old.
    seen = Bundle("seen")

    def __init__(self) -> None:
        """Start with an empty database and an empty notebook."""
        super().__init__()
        self.db = TimeSeriesDB()
        self.model: dict[str, list[Reading]] = {}
        self.max_ages: dict[str, timedelta] = {}

    @initialize(target=seen, batch=batches_of_readings())
    def start_with_a_few_temperatures(self, batch: list[Reading]) -> MultipleResults[datetime]:
        """Begin every story with a "temperature" series holding a few readings."""
        self.db.create_series("temperature")
        self.model["temperature"] = []
        return self.add_readings("temperature", batch)

    @rule(name=some_names())
    def create_series(self, name: str) -> None:
        """Make a series; a name that's already taken is refused with DuplicateSeriesError."""
        if name in self.model:
            with pytest.raises(DuplicateSeriesError):
                self.db.create_series(name)
        else:
            self.db.create_series(name)
            self.model[name] = []

    @rule(name=some_names())
    def delete_series(self, name: str) -> None:
        """Delete a series and its retention rule, or get SeriesNotFoundError if there's none."""
        if name in self.model:
            self.db.delete_series(name)
            del self.model[name]
            self.max_ages.pop(name, None)
        else:
            with pytest.raises(SeriesNotFoundError):
                self.db.delete_series(name)

    @rule(target=seen, name=some_names(), batch=batches_of_readings())
    def add_readings(self, name: str, batch: list[Reading]) -> MultipleResults[datetime]:
        """Add a few readings from any moments, in any order; the notebook adds them to its end."""
        for timestamp, value, tags in batch:
            if name in self.model:
                self.db.add_point(name, value=value, timestamp=timestamp, tags=tags)
                self.model[name].append((timestamp, value, tags))
            else:
                with pytest.raises(SeriesNotFoundError):
                    self.db.add_point(name, value=value, timestamp=timestamp, tags=tags)
        return multiple(*(timestamp for timestamp, _, _ in batch))

    @rule(
        name=some_names(),
        start=st.one_of(st.none(), seen, moments()),
        end=st.one_of(st.none(), seen, moments()),
    )
    def query_range(self, name: str, start: datetime | None, end: datetime | None) -> None:
        """Ask for the readings from start to end (both included, None = no limit), and get exactly those."""
        if name not in self.model:
            with pytest.raises(SeriesNotFoundError):
                self.db.query(name, start=start, end=end)
            return
        expected = [
            reading
            for reading in self.model[name]
            if (start is None or start <= reading[0]) and (end is None or reading[0] <= end)
        ]
        got = as_readings(self.db.query(name, start=start, end=end))
        assert same_readings_in_time_order(got, expected)

    @rule(name=some_names(), max_age=lengths_of_time())
    def set_retention(self, name: str, max_age: timedelta) -> None:
        """Give a series a retention rule: keep readings no older than ``max_age``."""
        if name in self.model:
            self.db.set_retention(name, max_age)
            self.max_ages[name] = max_age
        else:
            with pytest.raises(SeriesNotFoundError):
                self.db.set_retention(name, max_age)

    @rule(now=moments())
    def apply_retention(self, now: datetime) -> None:
        """Throw out old readings as if it were ``now``; the count removed matches the notebook."""
        removed = 0
        for name, max_age in self.max_ages.items():
            # A reading is kept if, at ``now``, it is no older than ``max_age``.
            # (A reading from the future has a negative age, so it stays.)
            kept = [reading for reading in self.model[name] if now - reading[0] <= max_age]
            removed += len(self.model[name]) - len(kept)
            self.model[name] = kept
        assert self.db.apply_retention(now=now) == removed

    @rule(name=some_names(), moment=seen)
    def apply_retention_on_the_dot(self, name: str, moment: datetime) -> None:
        """Throw out old readings at the very instant a reading from ``moment`` is exactly max_age old."""
        max_age = self.max_ages.get(name)
        if max_age is None or LAST_MOMENT - moment < max_age:
            return  # no rule, or that instant would be after year 9999
        self.apply_retention(now=moment + max_age)

    @invariant()
    def same_series_and_readings(self) -> None:
        """After every step, the database holds exactly the notebook's series and readings."""
        assert self.db.list_series() == sorted(self.model)
        assert self.db.series_count == len(self.model)
        for name, expected in self.model.items():
            series = self.db.get_series(name)
            assert len(series) == len(expected)
            assert same_readings_in_time_order(as_readings(self.db.query(name)), expected)
            if expected:
                assert series.first.timestamp == min(t for t, _, _ in expected)
                assert series.last.timestamp == max(t for t, _, _ in expected)
            else:
                with pytest.raises(EmptySeriesError):
                    _ = series.first
                with pytest.raises(EmptySeriesError):
                    _ = series.last


# why: 20 steps find the same bugs; 50 (the default) is most of the run time
TimeSeriesDBMachine.TestCase.settings = settings(stateful_step_count=20)
# pytest runs this like any other test class: one run plays 100 random stories.
# (Hypothesis doesn't say what type ``TestCase`` is, so ``cast`` tells pyright.)
TestTimeSeriesDBModel = cast("type[unittest.TestCase]", TimeSeriesDBMachine.TestCase)
