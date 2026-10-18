# Property Testing (No Reading Left Behind)

## The Logbook Auditor

Picture the weather station from the [home page](index.md). Every hour
someone reads the thermometer and writes the time and the temperature in
a logbook. At the end of the month, they boil it down into a summary:
one line per day, saying how many readings there were and what they
added up to. That's [downsampling](concepts/downsampling.md).

How would you check the summary is right? The usual way: write four
readings, summarise them by hour, and check the answer is the two numbers
you worked out by hand. That's an **example test**. It's useful, but it
only tells you about the four readings you thought of.

Now imagine an auditor. All day long they make up logbooks -- empty
ones, ones with a single reading from the year 1066, ones with three
readings at exactly the same second, ones written in no order at all --
and summarise each one with a different window: a microsecond, an hour,
a thousand years. For every single one they check one rule:

> However you summarise a logbook, no reading is lost and none is
> counted twice.

That rule is a **property**. It doesn't say what any one summary looks
like. It says something that must be true for *every* logbook.

When the auditor finds a logbook that breaks the rule, they don't just
report "something went wrong in a logbook with 40 readings in it". They
try again with fewer readings, simpler times and smaller numbers,
checking it still goes wrong each time, until the logbook is as small as
it can be. That boiling-down is called **shrinking**, and it's the best
part: the smallest failing input usually points straight at the bug.

In Python, the auditor is a library called
[Hypothesis](https://hypothesis.readthedocs.io/). PyTSDB's property tests
live in `tests/test_properties.py`, next to the ordinary example tests,
and the model check (more on that below) is in `tests/test_model.py`.

## A Property from PyTSDB

Here's the auditor's main rule, with the strategies that make its
logbooks:

```python
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
  from year 1 to year 9999, down to the microsecond. Sometimes two
  readings land on the same moment, and the list is in no particular order.
- **Why whole numbers?** Computers add decimals with tiny rounding
  errors: `0.1 + 0.2` is `0.30000000000000004`. Add the same readings in
  a different order and the last digit can change, even though both
  answers are "right". Whole numbers up to a million add up exactly, so
  the test can use `==` and any difference at all means a real bug.
- **`durations()`** makes the window: any positive length of time, from
  one microsecond to millions of days.
- **`@given(...)`** tells Hypothesis to run the test many times (100 in
  a normal run), each time with a fresh logbook and window.
- **The docstring** says the rule in plain English. If you can't say
  the rule in one sentence, it probably isn't a good property yet.
- **`counts_and_sums(logbook, window)`** is a small helper. It puts the
  readings into a `TimeSeriesDB` one by one, then downsamples twice:
  once with `AggFunc.COUNT` (how many readings in each bucket) and once
  with `AggFunc.SUM` (what they add up to).
- **`if downsampled is None: return`** covers the one refusal PyTSDB
  documents. Buckets line up with 1 January 1970, so a reading in the
  very first moments of year 1 can need a bucket that starts *before*
  year 1, and Python can't write that date down. `downsample` then
  raises `InvalidWindowError`. The helper checks the reading really is
  that early; a refusal for any other logbook fails the test.
- **The two `assert`s** are the rule itself: the bucket counts add up to
  the number of readings, and the bucket sums add up to the sum of all
  the readings. This kind of property is called an **invariant**:
  something that stays the same, however the logbook is chopped up.

Notice what the test *doesn't* say. It never says "readings at 9:00 and
9:30 make one hourly bucket of 2". It doesn't need to know any answers.
It only needs a rule that's always true.

Its partner, `test_each_bucket_holds_exactly_the_readings_in_its_window`,
checks each bucket on its own against a plain `sorted()` list: the bucket
starting at 9:00 must count and add up exactly the readings from 9:00 up
to (but not including) the next bucket. **A do-nothing `downsample` that
returns no buckets at all passes that one**, because with no buckets
there's nothing to check. That's why the counts-and-sums rule sits beside
it: no buckets means a count of 0, and it fails straight away.

| Rule | Test |
|---|---|
| Each bucket counts and adds up exactly the readings from its start to just before the next | `test_each_bucket_holds_exactly_the_readings_in_its_window` |
| Loading a saved database gives back the same series, readings, labels and retention rules | `test_save_then_load_gives_back_the_same_database` |
| Whatever bytes are in the file, loading gives a database or a `PersistenceError`, never another error | `test_any_bytes_on_disk_load_or_raise_persistence_error` |
| Whatever is in a save file's slots, loading gives a database or a `PersistenceError`, never another error | `test_damaged_save_file_load_or_raise_persistence_error` |

## Checking Against a Model

A property checks one action. But a database is something you change
step by step: make a series, add readings, ask questions, throw out old
readings, delete the series. Bugs often hide in the *order* of steps.

So the auditor has a second trick. They keep their own notebook, written
the simplest way possible: every reading just goes on the end of a list,
in the order it arrived, never sorted. After every step at the weather
station, they compare the database with the notebook. If the two ever
disagree, something's wrong with the database.

That notebook is a **model**: something simple that we already trust.
Here's part of the check in `tests/test_model.py`:

```python
class TimeSeriesDBMachine(RuleBasedStateMachine):
    """Play random steps on a TimeSeriesDB and on a dict of unsorted lists side by side."""

    seen = Bundle("seen")

    def __init__(self) -> None:
        """Start with an empty database and an empty notebook."""
        super().__init__()
        self.db = TimeSeriesDB()
        self.model: dict[str, list[Reading]] = {}
        self.max_ages: dict[str, timedelta] = {}

    @rule(target=seen, name=some_names(), batch=batches_of_readings())
    def add_readings(self, name: str, batch: list[Reading]) -> MultipleResults[datetime]:
        """Add a few readings from any moments, in any order; the notebook adds them to its end."""
        for timestamp, value, tags in batch:
            if name in self.model:
                self.db.add_point(name, value=value, timestamp=timestamp, tags=tags)
                self.model[name].append((timestamp, value, tags))
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
        assert self.db.list_series() == sorted(self.model)
        for name, expected in self.model.items():
            assert same_readings_in_time_order(as_readings(self.db.query(name)), expected)


TestTimeSeriesDBModel = cast("type[unittest.TestCase]", TimeSeriesDBMachine.TestCase)
```

Piece by piece:

- **`RuleBasedStateMachine`** is Hypothesis's tool for testing things
  that change step by step. Hypothesis makes up a random **story** of
  steps and plays it.
- **`self.db` and `self.model`** are the database and the notebook. The
  notebook is a plain dict: one unsorted list of readings per series,
  plus each series' retention rule in `self.max_ages`.
- **Each `@rule`** is one kind of step. It does the same thing to the
  database and the notebook. The real file has rules to make and delete
  series (including names that are taken or missing, which must raise
  the right error -- `add_readings` checks that too), add readings, query a time range, set retention
  rules and apply them. Every story starts with a `temperature` series
  holding a few readings, so there's always something to ask about.
- **`seen = Bundle("seen")`** is a bag of moments that readings were
  taken at. `add_readings` puts its timestamps in the bag
  (`target=seen`). Two random moments almost never match, so the query
  rule pulls its start and end from the bag too: that's how it tries
  asking for readings "up to 10:00" when one was taken at *exactly*
  10:00.
- **`apply_retention`** is a fake clock. Real retention asks the
  computer what time it is now; a test must never do that, or it would
  give different answers on different days. Here Hypothesis picks
  `now`, so a story can jump a thousand years in one step. The rule
  checks the answer that `apply_retention` *returns* (how many readings
  it threw out), not just what's left.
- **The `@invariant()`** runs after every single step and compares
  everything: which series exist, and every reading in each one.
  `same_readings_in_time_order` checks that the database gives back
  exactly the notebook's readings, oldest first.
- **`TestTimeSeriesDBModel = ...TestCase`** turns the machine into a test
  that pytest can find and run. One run plays 100 random stories, each
  up to 20 steps long.

The notebook is a good model because it's obviously right and it's
*not* PyTSDB's code. The database keeps its readings sorted and finds
time ranges with a binary search; the notebook never sorts anything, and
answers every question by looking at every reading. If we built the
model by copying the database, any bug would be in both, and they'd
agree perfectly about the wrong answer.

## Try It Yourself

Let's break downsampling on purpose and watch the auditor find it.

Open `src/pytsdb/aggregation.py`, find `_compute`, and change its last
line so "count" counts *different* values instead of readings:

```python
    return float(len(set(values)))  # was: return float(len(values))
```

Run the property tests:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

Hypothesis reports this (trimmed to the interesting part):

```
    @given(logbook=whole_number_logbooks(), window=durations())
    def test_downsampling_keeps_every_reading_exactly_once(
        logbook: list[tuple[datetime, float]], window: timedelta
    ) -> None:
        """However you downsample, the buckets' counts and sums add up to the whole logbook's."""
        downsampled = counts_and_sums(logbook, window)
        if downsampled is None:
            return  # refused for the one documented reason: see counts_and_sums
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

Look at how small that is. Hypothesis tried logbooks with dozens of
readings spread over thousands of years, then shrank them all the way
down to **two readings**: both at midnight on 1 January 2000, both
`0.0`. Two readings went in, the summary said 1. Two thermometers
showing the same temperature at the same time were counted as one.

Both downsampling properties catch it. The save/load, junk-file and
model checks stay green, because they never count anything.

The example tests all still pass. Only the property notices. Every
example in `tests/test_aggregation.py` uses four *different* readings,
so counting different values gives the same answer as counting
readings. Nobody thought to write two readings that match. The auditor
didn't need to think of it.

Put the line back to `return float(len(values))` and run the tests
again. They pass.

!!! tip "Older Hypothesis versions"
    Older versions of Hypothesis print `Falsifying example:` instead of
    `Failing test case:`. It means the same thing.

## A Bug We Found

When we first wrote
`test_each_bucket_holds_exactly_the_readings_in_its_window`, it failed on
PyTSDB's real code -- no deliberate bug needed:

```
E           assert 1.0 == 0
E            +  where 1.0 = DataPoint(timestamp=datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc), value=1.0, tags={}).value
E           Failing test case: test_each_bucket_holds_exactly_the_readings_in_its_window(
E               logbook=[(
E                    datetime.datetime(2000, 1, 1, 0, 0, 0, 1, tzinfo=datetime.timezone.utc),
E                    0.0,  # or any other generated value
E                )],
E               window=datetime.timedelta(microseconds=1),
E           )
```

One reading, taken one microsecond after midnight on 1 January 2000,
summarised into one-microsecond buckets. The bucket should start at
00:00:00.000001, exactly when the reading was taken. Instead it was
labelled 00:00:00 -- so the bucket ran from midnight to one microsecond
past, and *ended before its own reading*.

Here's why. The old code turned the time into a count of seconds,
stored as a float: `946684800.000001`. A float only has room for about
16 digits, and that number needs 16 with nothing to spare, so it was
stored as very slightly *less*. Dividing by the window and rounding down
then landed one bucket too early.

The example tests used tidy hourly windows and readings on the hour,
where the rounding never shows. The auditor tried a one-microsecond
window, which is exactly where it does.

The fix was to stop using floats. Python's `timedelta` counts whole
microseconds exactly, and you can divide one by another:

```python
    windows_since_epoch = (timestamp - epoch) // window  # was: total_seconds // window_seconds
```

The shrunk input became an ordinary example test,
`test_reading_on_a_bucket_boundary_starts_its_own_bucket` in
`tests/test_downsampling.py`, so this bug can never sneak back in.

It wasn't the only one. The other properties also found that `load`
crashed with the wrong error on a file that isn't text, on a reading
with 400 digits and on a retention period of zero, and the model check
found that retention crashed when asked to keep 2,000 years of readings
in the year 2000. All are fixed, and each one is pinned as an example
test.

## Run It Yourself

Run just the property tests and the model check (100 examples each, the
same every time):

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov
```

The `--no-cov` turns off the coverage check, which expects the *whole*
test suite to run and would fail on two files.

Run them the long way (2,000 random examples each, different every run)
to hunt for rarer bugs. It takes a few minutes:

```bash
uv run pytest tests/test_properties.py tests/test_model.py --no-cov --hypothesis-profile=thorough
```

The normal run uses a fixed seed, so it tries the same inputs every time
and a passing build means the same thing on every computer. The thorough
run is random, so each time you run it the auditor brings a brand-new
pile of logbooks. Both settings live in `conftest.py` at the top of the
project.

## Your Turn

Write one new property for PyTSDB. Think about downsampling with
`AggFunc.MAX`. Whatever the logbook and the window, how should the
biggest bucket compare with the biggest reading? What's the strategy?
(`whole_number_logbooks()` is a good start.) What's the `assert`? Run it
and watch it pass. Then break `max` in `_compute` on purpose and watch
the auditor find it.
