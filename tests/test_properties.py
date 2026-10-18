"""Property-based tests -- rules that must hold for *every* input.

An ordinary test checks one example someone thought of: "four half-hourly
readings, downsampled to hours, give two hourly averages". A property test
states a rule instead, such as "however you downsample, no reading is lost
or counted twice", and lets Hypothesis invent hundreds of logbooks to try
to break it. If one breaks the rule, Hypothesis *shrinks* it down to the
smallest input that still fails, and shows you that.

Each test below says its rule in plain English in its docstring. The
strategies at the top are recipes for making random inputs; each one is
named for what it makes.

The step-by-step check of ``TimeSeriesDB`` against a plain sorted list
lives in ``tests/test_model.py``. See ``docs/property-testing.md`` for the
walk-through.
"""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from pytsdb.aggregation import AggFunc
from pytsdb.database import TimeSeriesDB
from pytsdb.datapoint import DataPoint
from pytsdb.errors import InvalidWindowError, PersistenceError
from pytsdb.persistence import load, save
from tests.strategies import durations, readings, tag_sets, timestamps

# The very first moment a datetime can hold: midnight, 1 January, year 1.
FIRST_MOMENT = datetime.min.replace(tzinfo=UTC)

# A reading is (when, what value, which labels).
type Reading = tuple[datetime, float, dict[str, str]]

# --- Strategies: recipes for random inputs -----------------------------------
# timestamps(), readings(), tag_sets() and durations() live in
# tests/strategies.py, shared with the model check.


def series_names() -> st.SearchStrategy[str]:
    """Make any series name: empty, spaces, emoji, the lot."""
    return st.text()


def logbooks() -> st.SearchStrategy[list[Reading]]:
    """Make a pile of readings in any order, often with two at the same moment."""
    return st.lists(st.tuples(timestamps(), readings(), tag_sets()))


def whole_number_readings() -> st.SearchStrategy[float]:
    """Make a whole-number reading, like 21.0 or -7.0, between minus and plus a million."""
    # Adding up decimals like 0.1 + 0.2 gives tiny rounding errors that depend
    # on the order you add them in, so two correct answers can differ in the
    # last digit. Whole numbers this size add up exactly, so the sums below
    # can be compared with == and any difference at all is a real bug.
    return st.integers(min_value=-1_000_000, max_value=1_000_000).map(float)


def whole_number_logbooks() -> st.SearchStrategy[list[tuple[datetime, float]]]:
    """Make a pile of whole-number readings in any order."""
    return st.lists(st.tuples(timestamps(), whole_number_readings()))


def retention_periods() -> st.SearchStrategy[timedelta]:
    """Make a retention period from one microsecond up to about 272 years."""
    # RetentionPolicy.to_dict documents that a save file holds every
    # microsecond of the period exactly only up to 2**33 seconds.
    return st.timedeltas(
        min_value=timedelta(microseconds=1),
        max_value=timedelta(seconds=2**33) - timedelta(microseconds=1),
    )


def databases() -> st.SearchStrategy[dict[str, list[Reading]]]:
    """Make a whole database: up to three named series, each with its own logbook."""
    return st.dictionaries(series_names(), logbooks(), max_size=3)


def any_bytes() -> st.SearchStrategy[bytes]:
    """Make any run of raw bytes, including the empty one and ones that aren't text."""
    return st.binary()


def any_json_leaf() -> st.SearchStrategy[object]:
    """Make one plain JSON value: null, true/false, any number or any text."""
    return st.one_of(st.none(), st.booleans(), st.integers(), st.floats(), st.text())


def damaged_save_files() -> st.SearchStrategy[dict[str, object]]:
    """Make something shaped like a save file, but with any value in any slot."""
    point = st.fixed_dictionaries(
        {"timestamp": st.one_of(timestamps().map(datetime.isoformat), any_json_leaf())},
        optional={"value": any_json_leaf(), "tags": st.one_of(tag_sets(), any_json_leaf())},
    )
    series = st.fixed_dictionaries(
        {"name": st.one_of(series_names(), any_json_leaf())},
        optional={"points": st.one_of(st.lists(point, max_size=3), any_json_leaf())},
    )
    policy = st.fixed_dictionaries({}, optional={"max_age_seconds": any_json_leaf()})
    return st.fixed_dictionaries(
        {"series": st.dictionaries(st.text(), series, max_size=2)},
        optional={"retention": st.dictionaries(st.text(), policy, max_size=2)},
    )


# --- Helpers -----------------------------------------------------------------


def database_holding(contents: dict[str, list[Reading]]) -> TimeSeriesDB:
    """Return a TimeSeriesDB with one series per name, holding those readings."""
    db = TimeSeriesDB()
    for name, logbook in contents.items():
        db.create_series(name)
        for timestamp, value, tags in logbook:
            db.add_point(name, value=value, timestamp=timestamp, tags=tags)
    return db


def everything_in(db: TimeSeriesDB) -> dict[str, list[Reading]]:
    """Return every series' readings, in the order the database keeps them."""
    return {
        name: [(p.timestamp, p.value, p.tags) for p in db.query(name)] for name in db.list_series()
    }


def retention_rules(db: TimeSeriesDB) -> dict[str, timedelta]:
    """Return how long each series with a retention rule keeps its readings."""
    return {name: policy.max_age for name, policy in db._retention.items()}


def counts_and_sums(
    logbook: list[tuple[datetime, float]], window: timedelta
) -> tuple[list[DataPoint], list[DataPoint]] | None:
    """Put the readings in a series, then downsample it twice: bucket counts, then bucket sums.

    Returns None if downsampling is refused for the one reason ``aggregate``
    documents: buckets line up with 1 January 1970, so a reading less than
    one window after the very first moment of year 1 can need a bucket that
    starts before year 1, which a datetime can't hold. A refusal for any
    other reading fails the test.
    """
    db = TimeSeriesDB()
    db.create_series("weather")
    for timestamp, value in logbook:
        db.add_point("weather", value=value, timestamp=timestamp)
    try:
        counts = db.downsample("weather", window, func=AggFunc.COUNT)
        sums = db.downsample("weather", window, func=AggFunc.SUM)
    except InvalidWindowError:
        assert min(timestamp for timestamp, _ in logbook) - FIRST_MOMENT < window
        return None
    return counts, sums


def load_or_refuse(path: Path) -> None:
    """Load the database at ``path``, accepting only a PersistenceError refusal.

    A PersistenceError is caught and ignored: refusing a bad file is fine. Any
    *other* exception escapes and fails the test, and that is the whole check.
    """
    try:
        load(path)
    except PersistenceError:
        return


# --- Downsampling: every reading lands in exactly one bucket ------------------


@given(logbook=whole_number_logbooks(), window=durations())
def test_downsampling_keeps_every_reading_exactly_once(
    logbook: list[tuple[datetime, float]], window: timedelta
) -> None:
    """However you downsample, the buckets' counts and sums add up to the whole logbook's."""
    downsampled = counts_and_sums(logbook, window)
    if downsampled is None:
        return  # refused for the one documented reason: see counts_and_sums
    counts, sums = downsampled

    assert sum(bucket.value for bucket in counts) == len(logbook)
    assert sum(bucket.value for bucket in sums) == sum(value for _, value in logbook)


@given(logbook=whole_number_logbooks(), window=durations())
def test_each_bucket_holds_exactly_the_readings_in_its_window(
    logbook: list[tuple[datetime, float]], window: timedelta
) -> None:
    """Each bucket counts and adds up exactly the readings from its start to just before the next."""
    downsampled = counts_and_sums(logbook, window)
    if downsampled is None:
        return  # refused for the one documented reason: see counts_and_sums
    counts, sums = downsampled
    in_order = sorted(logbook)

    assert [bucket.timestamp for bucket in counts] == [bucket.timestamp for bucket in sums]
    for count, total in zip(counts, sums, strict=True):
        start = count.timestamp
        # ``timestamp - start < window`` rather than ``timestamp < start + window``,
        # because ``start + window`` can run off the end of the calendar (year 9999).
        inside = [
            value for timestamp, value in in_order if timedelta(0) <= timestamp - start < window
        ]
        assert count.value == len(inside)
        assert total.value == sum(inside)


# --- Save and load: whatever you hand in comes back --------------------------


@given(contents=databases(), max_ages=st.lists(st.one_of(st.none(), retention_periods())))
def test_save_then_load_gives_back_the_same_database(
    contents: dict[str, list[Reading]], max_ages: list[timedelta | None]
) -> None:
    """Loading a saved database gives back the same series, readings, labels and retention rules."""
    db = database_holding(contents)
    # Give each series in turn a retention rule from ``max_ages``, or none for ``None``.
    for name, max_age in zip(contents, max_ages, strict=False):
        if max_age is not None:
            db.set_retention(name, max_age)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "db.json"
        save(db, path)
        loaded = load(path)
    # ``repr`` tells 1 from 1.0, -0.0 from 0.0 and one timezone from another,
    # which ``==`` doesn't, so it checks every reading exactly.
    assert repr(everything_in(loaded)) == repr(everything_in(db))
    assert retention_rules(loaded) == retention_rules(db)


# --- Loading junk: a bad save file is refused, never a crash ------------------


@given(junk=any_bytes())
def test_any_bytes_on_disk_load_or_raise_persistence_error(junk: bytes) -> None:
    """Whatever bytes are in the file, loading gives a database or a PersistenceError, never another error."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "db.json"
        path.write_bytes(junk)
        load_or_refuse(path)


@given(document=damaged_save_files())
def test_damaged_save_file_load_or_raise_persistence_error(document: dict[str, object]) -> None:
    """Whatever is in a save file's slots, loading gives a database or a PersistenceError, never another error."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "db.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        load_or_refuse(path)
