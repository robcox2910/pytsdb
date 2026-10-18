# Property Testing (No Reading Left Behind)

## The Logbook Auditor

Picture the weather station from the [home page](index.md). Every hour
someone reads the thermometer and writes the time and temperature in a
logbook. At the end of the month, they boil it down into a summary: one
line per day, saying how many readings there were and what they added up
to. That's [downsampling](concepts/downsampling.md).

How would you check the summary is right? The usual way: write four
readings, summarise them by hour, and check the answer against numbers
you worked out by hand. That's an **example test**, and it only tells you
about the four readings you thought of.

Now imagine an auditor who makes up logbooks all day -- empty ones, ones
with a single reading from the year 1066, ones with three readings at
exactly the same second, ones in no order at all -- and summarises each
with a different window: a microsecond, an hour, a thousand years. For
every one they check one rule:

> However you summarise a logbook, no reading is lost and none is
> counted twice.

That rule is a **property**. It doesn't say what any one summary looks
like, only what must be true for *every* logbook.

When the auditor finds a logbook that breaks the rule, they don't just
report "something went wrong in a logbook with 40 readings in it". They
retry with fewer readings, simpler times and smaller numbers, as long as
it still goes wrong, until the logbook is as small as it can be. That
boiling-down is called **shrinking**, and the smallest failing input
usually points straight at the bug.

In Python, the auditor is a library called
[Hypothesis](https://hypothesis.readthedocs.io/). PyTSDB's property tests
live in `tests/test_properties.py`, and the model check (more below) is
in `tests/test_model.py`.

## A Property from PyTSDB

Here's the auditor's main rule, with the strategies that make its
logbooks:

```python
def whole_number_readings() -> st.SearchStrategy[float]:
    """Make a whole-number reading, like 21.0 or -7.0, between minus and plus a million."""
    # Whole numbers this size add up exactly, so the sums below can be
    # compared with == and any difference at all is a real bug.
    return st.integers(min_value=-1_000_000, max_value=1_000_000).map(float)


def whole_number_logbooks() -> st.SearchStrategy[list[tuple[datetime, float]]]:
    """Make a pile of whole-number readings in any order."""
    return st.lists(st.tuples(timestamps(), whole_number_readings()))


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
```

Line by line:

- **`whole_number_readings()` and `whole_number_logbooks()`** are
  **strategies**: recipes for making random inputs. A logbook is a list
  of `(timestamp, reading)` pairs. `timestamps()` (in
  `tests/strategies.py`, shared with the model check) makes any moment
  from year 1 to year 9999, to the microsecond. Sometimes two readings
  land on the same moment, and the list is in no particular order.
- **Why whole numbers?** Decimals add up with tiny rounding errors
  (`0.1 + 0.2` is `0.30000000000000004`) that change with the order.
  Whole numbers up to a million add up exactly, so the test can use `==`
  and any difference at all means a real bug.
- **`durations()`** makes the window: any positive length of time, from a
  microsecond to millions of days.
- **`@given(...)`** runs the test many times (100 in a normal run), each
  with a fresh logbook and window.
- **The docstring** says the rule in plain English. If you can't say it
  in one sentence, it probably isn't a good property yet.
- **`counts_and_sums(logbook, window)`** is a small helper. It puts the
  readings into a `TimeSeriesDB`, then downsamples twice: with
  `AggFunc.COUNT` (readings per bucket) and `AggFunc.SUM` (what they add
  up to).
- **`if downsampled is None: return`** covers the one refusal PyTSDB
  documents. Buckets line up with 1 January 1970, so a reading in the
  first moments of year 1 can need a bucket starting *before* year 1,
  which Python can't write down, and `downsample` raises
  `InvalidWindowError`. The helper checks the reading really is that
  early; a refusal for any other logbook fails the test.
- **The two `assert`s** are the rule itself: the bucket counts add up to
  the number of readings, and the bucket sums to the sum of all the
  readings. That's an **invariant**: something that stays the same,
  however the logbook is chopped up.

Notice what the test *doesn't* say: it never says "readings at 9:00 and
9:30 make one hourly bucket of 2". It needs no answers, only a rule
that's always true.

Its partner, `test_each_bucket_holds_exactly_the_readings_in_its_window`,
checks each bucket against a plain `sorted()` list: the bucket starting
at 9:00 must count and add up exactly the readings from 9:00 up to (but
not including) the next bucket, and every bucket must start a whole
number of windows after midnight on 1 January 1970, as `aggregate`
promises. **A do-nothing `downsample` that returns no buckets passes that
one**, because there's nothing to check. That's why the counts-and-sums
rule sits beside it: no buckets means a count of 0, and it fails
straight away.

| Rule | Test |
|---|---|
| Each bucket starts a whole number of windows after 1970 and holds exactly the readings up to the next | `test_each_bucket_holds_exactly_the_readings_in_its_window` |
| Loading a saved database gives back the same series, readings, labels and retention rules | `test_save_then_load_gives_back_the_same_database` |
| Whatever bytes are in the file, loading gives a database or a `PersistenceError`, never another error | `test_any_bytes_on_disk_load_or_raise_persistence_error` |
| Whatever is in a save file's slots, loading gives a whole, working database or a `PersistenceError` | `test_damaged_save_file_load_or_raise_persistence_error` |

## Checking Against a Model

A property checks one action. But a database changes step by step, and
bugs often hide in the *order* of steps: make a series, add readings, ask
questions, throw out old readings, delete the series.

So the auditor has a second trick: their own notebook, written the
simplest way possible, with every reading just added to the end of a list
in the order it arrived. After every step they compare the database with
the notebook. If the two ever disagree, something's wrong with the
database.

That notebook is a **model**: something simple that we already trust.
Here's part of the check in `tests/test_model.py`:

```python
class TimeSeriesDBMachine(RuleBasedStateMachine):
    seen = Bundle("seen")

    def __init__(self) -> None:
        """Start with an empty database and an empty notebook."""
        super().__init__()
        self.db = TimeSeriesDB()
        self.model: dict[str, list[Reading]] = {}
        self.max_ages: dict[str, timedelta] = {}

    @rule(target=seen, name=some_names(), batch=batches_of_readings())
    def add_readings(self, name: str, batch: list[Reading]) -> MultipleResults[datetime]:
        """Add a few readings, in any order; the notebook adds them to its end."""
        for timestamp, value, tags in batch:
            handed_in = dict(tags)
            if name in self.model:
                added = self.db.add_point(name, value=value, timestamp=timestamp, tags=handed_in)
                self.model[name].append((timestamp, value, dict(tags)))
                handed_in["scribble"] = "!"
                added.tags["scribble"] = "!"
        return multiple(*(timestamp for timestamp, _, _ in batch))

    @rule(now=moments())
    def apply_retention(self, now: datetime) -> None:
        """Throw out old readings as if it were ``now``; the count removed matches the notebook."""
        removed = 0
        for name, max_age in self.max_ages.items():
            kept = [reading for reading in self.model[name] if now - reading[0] <= max_age]
            removed += len(self.model[name]) - len(kept)
            self.model[name] = kept
        assert self.db.apply_retention(now=now) == removed

    @invariant()
    def same_series_and_readings(self) -> None:
        """After every step, the database holds exactly the notebook's series and readings."""
        for name, notebook in self.model.items():
            expected = oldest_first(notebook)
            assert same(as_readings(self.db.query(name)), expected)

TestTimeSeriesDBModel = cast("type[unittest.TestCase]", TimeSeriesDBMachine.TestCase)
```

Piece by piece:

- **`RuleBasedStateMachine`** is Hypothesis's tool for things that change
  step by step. It makes up a random **story** of steps and plays it.
- **`self.db` and `self.model`** are the database and the notebook: a
  plain dict with one unsorted list of readings per series, plus each
  series' retention rule in `self.max_ages`.
- **Each `@rule`** is one kind of step, done to both the database and
  the notebook. `add_readings` also scribbles on the labels it handed in
  and on the point it got back: if the database had kept either dict, the
  next check would see the scribble. The real file has
  rules to make and delete series, query by time and by label, work out
  the rate of change, count and find the biggest reading per window, set
  retention rules and apply them, and scribble on everything a read
  hands back. Asking for a series that isn't there must raise
  `SeriesNotFoundError`. Every story starts with a `temperature` series
  holding a few readings.
- **`seen = Bundle("seen")`** is a bag of moments that readings were
  taken at; `add_readings` fills it (`target=seen`). Two random moments
  almost never match, so the query rule pulls its start and end from the
  bag: that's how it asks for readings "up to 10:00" when one was taken
  at *exactly* 10:00.
- **`apply_retention`** is a fake clock. Real retention asks the computer
  for the time, which would differ from day to day. Here Hypothesis picks `now`, so a story can jump a thousand years in
  one step. The rule checks what `apply_retention` *returns* (how many
  readings it threw out), not just what's left.
- **The `@invariant()`** runs after every step and compares everything:
  here, every reading in each series. `oldest_first` sorts the notebook
  with Python's `sorted()`, which never swaps two readings from the same
  moment, and `same` compares the answers exactly, labels and all. The
  real file also checks which series exist, `first`, `last` and looping
  over a series.
- **`TestTimeSeriesDBModel = ...TestCase`** turns the machine into a test
  pytest can run. One run plays 100 random stories of up to 20 steps.

The notebook is a good model because it's obviously right and *not*
PyTSDB's code. The database keeps readings in order and finds time
ranges with a binary search; the notebook answers every question by
looking at every reading. A model copied from the database would share
its bugs, and they'd agree perfectly about the wrong answer.

## Try It Yourself

Let's break downsampling on purpose and watch the auditor find it.

In `src/pytsdb/aggregation.py`, change the last line of `_compute` so
"count" counts *different* values instead of readings:

```python
    return float(len(set(values)))  # was: return float(len(values))
```

Run the property tests:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

Hypothesis reports (trimmed):

```
        counts, sums = downsampled

>       assert sum(bucket.value for bucket in counts) == len(logbook)
E       assert 1.0 == 2
E       Failing test case: test_downsampling_keeps_every_reading_exactly_once(
E           logbook=[(datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
E                0.0),
E            (datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc), 0.0)],
E           window=datetime.timedelta(microseconds=1),  # or any other generated value
E       )
```

Hypothesis tried logbooks with dozens of readings over thousands of
years, then shrank them to **two readings**: both at midnight on 1 January 2000, both
`0.0`. Two readings went in, the summary said 1: two thermometers showing the
same temperature at the same time were counted as one.

Both downsampling properties catch it. The save/load and junk-file
properties stay green: they never count anything. The model check
counts, but its 100 stories happen to miss this one.

The example tests all still pass. Every example in
`tests/test_aggregation.py` uses four *different* readings, so counting
different values gives the same answer as counting readings. Nobody
thought to write two readings that match. The auditor didn't need to.

Put the line back to `return float(len(values))` and the tests pass.

!!! tip "Older Hypothesis versions"
    Older Hypothesis versions print `Falsifying example:` instead of
    `Failing test case:`. Same thing.

## A Bug We Found

`test_each_bucket_holds_exactly_the_readings_in_its_window` failed on
PyTSDB's real code on its first run -- no deliberate bug needed:

```
    assert count.value == len(inside)
AssertionError: assert 1.0 == 0
 +  where 1.0 = DataPoint(timestamp=datetime.datetime(1999, 12, 31, 23, 59, 59, 999875, tzinfo=datetime.timezone.utc), value=1.0, tags={}).value
 +  and   0 = len([])
Failing test case: test_each_bucket_holds_exactly_the_readings_in_its_window(
    logbook=[(
         datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc),
         0.0,  # or any other generated value
     )],
    window=datetime.timedelta(microseconds=125),
)
```

One reading, at midnight on 1 January 2000, summarised into
125-microsecond buckets. Its bucket should start at midnight. Instead it
was labelled 23:59:59.999875, the year before, so the bucket *ended* just
before its own reading.

Here's why. The old code counted windows in float seconds, and 0.000125
can't be stored exactly as a float: it's kept a hair *bigger*. So the
division comes out a hair under the whole number 7,573,478,400,000, and
rounding down (`//`) lands one bucket too early.

The example tests used tidy hourly windows, where the rounding never
shows; the auditor tried 125 microseconds.

The fix was to stop using floats: `timedelta` counts whole microseconds
exactly, and you can divide one by another. Before:

```python
    bucket_start = int(total_seconds // window_seconds) * window_seconds
    return epoch + timedelta(seconds=bucket_start)
```

After (the `try` is there for the year-1 limit):

```python
    windows_since_epoch = (timestamp - epoch) // window
    try:
        return epoch + windows_since_epoch * window
```

The shrunk input became an example test in
`tests/test_downsampling.py`, so this bug can't sneak back in:

```python
def test_reading_on_a_bucket_boundary_starts_its_own_bucket() -> None:
    midnight = datetime(2000, 1, 1, tzinfo=UTC)
    result = downsample(
        [DataPoint(timestamp=midnight, value=VALUE_10)], target_interval=timedelta(microseconds=125)
    )
    assert [bucket.timestamp for bucket in result] == [midnight]
```

It wasn't the only one. The properties and the model check also found
that `load` crashed with the wrong error on damaged files, that a save
file could hold two series with one name, that retention crashed when
asked to keep 2,000 years of readings, that tags handed back by `query`
could change the database, and that a NaN reading jumbled the order of
readings. All are fixed and pinned as example tests.

## Run It Yourself

Run the property tests and the model check (100 examples each, the same
every time):

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

`--no-cov` turns off the coverage check, which expects the *whole* suite.

Run them the long way (2,000 random examples each, different every run)
to hunt for rarer bugs, in a few minutes:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov --hypothesis-profile=thorough
```

The normal run uses a fixed seed, so a passing build means the same
thing on every computer. The thorough run is random: each time, the
auditor brings a brand-new pile of logbooks. Both settings live in
`conftest.py` at the top of the project.

## Your Turn

Write one new property for PyTSDB, about downsampling with
`AggFunc.MAX`. Whatever the logbook and the window, how should the
biggest bucket compare with the biggest reading? What's the strategy
(`whole_number_logbooks()` is a good start) and the `assert`? Run it and
watch it pass. Then break `max` in `_compute` on purpose and watch the
auditor find it.
