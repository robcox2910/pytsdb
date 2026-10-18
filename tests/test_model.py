"""Model check -- TimeSeriesDB must behave like a plain list of readings.

A property test checks one rule for many inputs. A *model check* goes
further: Hypothesis invents a random *story* -- make a series, add a
reading from last Tuesday, add one from 1850, ask for everything in June,
throw out old readings, delete the series -- and plays it on two things at
once:

- the real ``TimeSeriesDB``;
- a **model**: a dict of plain Python lists, one unsorted list of
  ``(timestamp, value, tags)`` per series, which we already trust.

Every read the database offers is checked against the notebook: queries
by time and by label, ``first``/``last``, looping over a series, rate of
change, windowed aggregates, ``list_series`` and asking for a series that
isn't there.

After every step the two must agree. If they ever disagree, Hypothesis
shrinks the story to the shortest list of steps that still goes wrong.

The model is deliberately *not* a copy of ``TimeSeriesDB``'s code. It
never sorts anything as it goes and never uses binary search: it keeps
readings in the order they arrived and, when asked a question, simply
looks at every one (sorting with ``sorted()`` only to answer "oldest first"). So when the two disagree, the database is the one to
suspect.

Retention ("throw out readings older than 30 days") normally reads the
real clock, which a model check must never do. Here every
``apply_retention`` call is handed a made-up "now", so the story can jump
across centuries in an instant.

See ``docs/property-testing.md`` for the walk-through.
"""

import unittest
from datetime import UTC, datetime, timedelta
from itertools import pairwise
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

from pytsdb.aggregation import AggFunc
from pytsdb.database import TimeSeriesDB
from pytsdb.datapoint import DataPoint
from pytsdb.errors import (
    DuplicateSeriesError,
    EmptySeriesError,
    InvalidWindowError,
    SeriesNotFoundError,
)
from tests.strategies import durations, readings, tag_sets, timestamps

# The very first and last moments a datetime can hold: midnight on
# 1 January of year 1, and just before midnight on 31 December 9999.
FIRST_MOMENT = datetime.min.replace(tzinfo=UTC)
LAST_MOMENT = datetime.max.replace(tzinfo=UTC)

# Buckets line up with midnight on 1 January 1970, as ``aggregate`` documents.
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

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


def maybe_moments() -> st.SearchStrategy[datetime | None]:
    """Make a moment, or None for "no limit"."""
    return st.one_of(st.none(), moments())


def whole_hours() -> st.SearchStrategy[timedelta]:
    """Make a length of time from 1 to 5 whole hours."""
    return st.builds(timedelta, hours=st.integers(min_value=1, max_value=5))


def lengths_of_time() -> st.SearchStrategy[timedelta]:
    """Make a length of time that's often whole hours, and sometimes any positive length."""
    return st.one_of(whole_hours(), durations())


def room_labels() -> st.SearchStrategy[dict[str, str]]:
    """Make up to two labels from a tiny choice, like ``{"room": "hall"}``, so filters often match."""
    return st.dictionaries(
        st.sampled_from(["room", "floor"]), st.sampled_from(["hall", "1"]), max_size=2
    )


def labels() -> st.SearchStrategy[dict[str, str]]:
    """Make labels that are often from the tiny choice, and sometimes any labels at all."""
    return st.one_of(room_labels(), tag_sets())


def some_names() -> st.SearchStrategy[str]:
    """Pick one of three series names, so the same name comes up again and again."""
    # Any text works as a name (the save/load property tries all sorts), but
    # three names mean the story keeps coming back to the same series.
    return st.sampled_from(["temperature", "rain", ""])


def batches_of_readings() -> st.SearchStrategy[list[Reading]]:
    """Make one to five readings, in no particular order."""
    return st.lists(st.tuples(moments(), readings(), labels()), min_size=1, max_size=5)


def as_readings(points: list[DataPoint]) -> list[Reading]:
    """Turn the database's data points into plain (timestamp, value, tags) tuples."""
    return [(p.timestamp, p.value, p.tags) for p in points]


def oldest_first(notebook: list[Reading]) -> list[Reading]:
    """Return the readings oldest first; ones from the same moment stay in arrival order."""
    # ``sorted`` never swaps two readings it thinks are equal, so readings
    # from the same moment keep the order they were written in.
    return sorted(notebook, key=lambda reading: reading[0])


def same(got: object, expected: object) -> bool:
    """Say whether two answers are exactly the same, down to 1 versus 1.0 and -0.0 versus 0.0."""
    return repr(got) == repr(expected)


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
        """Add a few readings, in any order; the notebook adds them to its end."""
        for timestamp, value, tags in batch:
            handed_in = dict(tags)
            if name in self.model:
                added = self.db.add_point(name, value=value, timestamp=timestamp, tags=handed_in)
                self.model[name].append((timestamp, value, dict(tags)))
                # Scribble on the labels we handed in and on the point we got
                # back: neither may change what the database stored.
                handed_in["scribble"] = "!"
                added.tags["scribble"] = "!"
            else:
                with pytest.raises(SeriesNotFoundError):
                    self.db.add_point(name, value=value, timestamp=timestamp, tags=handed_in)
        return multiple(*(timestamp for timestamp, _, _ in batch))

    @rule(
        name=some_names(),
        start=st.one_of(st.none(), seen, moments()),
        end=st.one_of(st.none(), seen, moments()),
        tags=st.one_of(st.none(), room_labels()),
    )
    def query(
        self,
        name: str,
        start: datetime | None,
        end: datetime | None,
        tags: dict[str, str] | None,
    ) -> None:
        """Ask for readings from start to end (both included) with these labels; get exactly those."""
        if name not in self.model:
            with pytest.raises(SeriesNotFoundError):
                self.db.query(name, start=start, end=end, tags=tags)
            with pytest.raises(SeriesNotFoundError):
                self.db.get_series(name)
            return
        expected = [
            reading
            for reading in oldest_first(self.model[name])
            if (start is None or start <= reading[0])
            and (end is None or reading[0] <= end)
            and (tags is None or tags.items() <= reading[2].items())
        ]
        got = as_readings(self.db.query(name, start=start, end=end, tags=tags))
        assert same(got, expected)

    @rule(name=some_names())
    def scribble_on_answers(self, name: str) -> None:
        """Scribble on the labels of every point we're handed; the database must not change."""
        if name not in self.model:
            return
        series = self.db.get_series(name)
        handed_out = [*self.db.query(name), *series, *series.points]
        if self.model[name]:
            handed_out += [series.first, series.last]
        for point in handed_out:
            point.tags["scribble"] = "!"

    @rule(name=some_names())
    def rate_of_change(self, name: str) -> None:
        """Each rate is the change in value per second between neighbours at different moments."""
        if name not in self.model:
            with pytest.raises(SeriesNotFoundError):
                self.db.rate_of_change(name)
            return
        ordered = oldest_first(self.model[name])
        expected = [
            (later[0], (later[1] - earlier[1]) / (later[0] - earlier[0]).total_seconds())
            for earlier, later in pairwise(ordered)
            if later[0] != earlier[0]
        ]
        got = [(p.timestamp, p.value) for p in self.db.rate_of_change(name)]
        assert same(got, expected)

    @rule(name=some_names(), window=lengths_of_time(), start=maybe_moments(), end=maybe_moments())
    def aggregate(
        self, name: str, window: timedelta, start: datetime | None, end: datetime | None
    ) -> None:
        """Count and take the biggest reading per window, for readings from start to end."""
        if name not in self.model:
            with pytest.raises(SeriesNotFoundError):
                self.db.aggregate(name, window, AggFunc.COUNT, start=start, end=end)
            return
        # Oldest first, so that of two equal biggest readings (like 0.0 and
        # -0.0) the one that comes first in time is the one we expect.
        in_range = [
            (timestamp, value)
            for timestamp, value, _ in oldest_first(self.model[name])
            if (start is None or start <= timestamp) and (end is None or timestamp <= end)
        ]
        try:
            counts = self.db.aggregate(name, window, AggFunc.COUNT, start=start, end=end)
            biggest = self.db.aggregate(name, window, AggFunc.MAX, start=start, end=end)
        except InvalidWindowError:
            # The one documented refusal: a bucket that would start before year 1.
            assert min(timestamp for timestamp, _ in in_range) - FIRST_MOMENT < window
            return
        assert sum(bucket.value for bucket in counts) == len(in_range)
        assert [b.timestamp for b in counts] == [b.timestamp for b in biggest]
        for count, top in zip(counts, biggest, strict=True):
            start_of_bucket = count.timestamp
            assert (start_of_bucket - EPOCH) % window == timedelta(0)
            inside = [v for t, v in in_range if timedelta(0) <= t - start_of_bucket < window]
            assert count.value == len(inside)
            assert same(top.value, max(inside))

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

    @rule(name=some_names(), max_age=lengths_of_time(), moment=seen)
    def apply_retention_on_the_dot(self, name: str, max_age: timedelta, moment: datetime) -> None:
        """Set a retention rule, then apply it at the instant a reading from ``moment`` is exactly that old."""
        if name not in self.model or LAST_MOMENT - moment < max_age:
            return  # no such series, or that instant would be after year 9999
        self.set_retention(name, max_age)
        self.apply_retention(now=moment + max_age)

    @invariant()
    def same_series_and_readings(self) -> None:
        """After every step, the database holds exactly the notebook's series and readings."""
        assert self.db.list_series() == sorted(self.model)
        assert self.db.series_count == len(self.model)
        for name, notebook in self.model.items():
            expected = oldest_first(notebook)
            series = self.db.get_series(name)
            assert len(series) == len(expected)
            assert same(as_readings(self.db.query(name)), expected)
            assert same(as_readings(list(series)), expected)
            if expected:
                assert same(as_readings([series.first, series.last]), [expected[0], expected[-1]])
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
