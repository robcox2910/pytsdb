# pytsdb

An educational time-series database built from scratch in Python. Part of the **PyLearn** platform for kids aged 12+.

A time-series database stores data points that each have a **timestamp**, a **value**, and optional **tags** -- like a weather station logbook that records temperature readings throughout the day.

## Features

- **DataPoint** -- timestamped values with optional tags (e.g. sensor="kitchen")
- **TimeSeries** -- ordered collection of data points for one metric
- **TimeSeriesDB** -- container managing multiple named series with full CRUD
- **Time Range Queries** -- efficient binary-search lookups between two timestamps
- **Tag Filtering** -- filter data points by tag key-value pairs
- **Aggregation** -- compute avg, min, max, sum, count over configurable time windows
- **Downsampling** -- reduce resolution (e.g. minute data to hourly averages)
- **Retention Policies** -- auto-delete data older than N days
- **Persistence** -- save/load the entire database to JSON files
- **Rate of Change** -- compute how fast a value is changing over time

## Quick Start

```python
from datetime import datetime, timedelta, timezone
from pytsdb import AggFunc, TimeSeriesDB

# Create a database and a series
db = TimeSeriesDB()
db.create_series("temperature")

# Add some readings
db.add_point("temperature", value=68.0,
             timestamp=datetime(2024, 7, 4, 8, 0, tzinfo=timezone.utc),
             tags={"sensor": "kitchen"})
db.add_point("temperature", value=72.5,
             timestamp=datetime(2024, 7, 4, 10, 0, tzinfo=timezone.utc),
             tags={"sensor": "kitchen"})
db.add_point("temperature", value=75.0,
             timestamp=datetime(2024, 7, 4, 12, 0, tzinfo=timezone.utc),
             tags={"sensor": "bedroom"})

# Query by time range and tags
kitchen = db.query("temperature", tags={"sensor": "kitchen"})
print(f"Kitchen readings: {len(kitchen)}")  # 2

# Aggregate: hourly averages
hourly = db.aggregate("temperature", window=timedelta(hours=1), func=AggFunc.AVG)

# Downsample to 2-hour buckets
coarse = db.downsample("temperature", target_interval=timedelta(hours=2))

# Auto-expire old data
db.set_retention("temperature", max_age=timedelta(days=30))
db.apply_retention()

# Save to disk
from pytsdb import save, load
save(db, "my_data.json")
db2 = load("my_data.json")
```

## Concepts

See the [docs/](docs/) folder for kid-friendly explanations with real-world analogies:

- [What is a Time-Series DB?](docs/index.md) -- weather station logbook analogy
- [Data Points](docs/concepts/datapoints.md) -- thermometer readings
- [Time Series](docs/concepts/series.md) -- a week of readings
- [Queries](docs/concepts/queries.md) -- checking yesterday's weather
- [Aggregation](docs/concepts/aggregation.md) -- weekly average temperature
- [Downsampling](docs/concepts/downsampling.md) -- monthly summaries
- [Retention](docs/concepts/retention.md) -- throwing away old newspapers

<!-- docs:start -->
## Documentation

Full docs (with kid-friendly explanations of every idea): https://robcox2910.github.io/pytsdb/

## Install

[![PyPI](https://img.shields.io/pypi/v/fromscratch-pytsdb)](https://pypi.org/project/fromscratch-pytsdb/)

```bash
pip install fromscratch-pytsdb
```

Or get the whole series at once: `pip install fromscratch-pystack`.
<!-- docs:end -->

## Development

```bash
uv sync --all-extras
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pyright src tests
uv run pytest
```

## Releasing

Other projects in the series ([PyStack](https://github.com/robcox2910/pystack)) use a released version of this one from PyPI,
not whatever is on `main`. To publish a change for them:

1. Merge the change to `main`.
2. Release it: `gh release create vX.Y.Z --target main --generate-notes`
   (or push a `vX.Y.Z` tag); the release workflow publishes it to PyPI.
   A change to the public API bumps the minor version (`v0.1.0` → `v0.2.0`);
   anything else bumps the patch (`v0.1.0` → `v0.1.1`).
3. In each project that uses it, raise the `fromscratch-pytsdb>=X.Y.Z` floor in
   `pyproject.toml`, run `uv lock --upgrade-package fromscratch-pytsdb`, and open
   a pull request so CI checks the pair together.

<!-- series:start -->
## Related Projects

This project is one of a series that builds real systems "from scratch in Python" to teach how they work. See the [series home](https://robcox2910.github.io/) for the full story.

| Project | What it teaches | Repository | Docs | PyPI |
| --- | --- | --- | --- | --- |
| PyOS | Operating systems | [py-os](https://github.com/robcox2910/py-os) | [Docs](https://robcox2910.github.io/py-os/) | [fromscratch-pyos](https://pypi.org/project/fromscratch-pyos/) |
| Pebble | Compilers and programming languages | [pebble-lang](https://github.com/robcox2910/pebble-lang) | [Docs](https://robcox2910.github.io/pebble-lang/) | [fromscratch-pebble](https://pypi.org/project/fromscratch-pebble/) |
| PyDB | Relational databases | [pydb](https://github.com/robcox2910/pydb) | [Docs](https://robcox2910.github.io/pydb/) | [fromscratch-pydb](https://pypi.org/project/fromscratch-pydb/) |
| PyKV | Key-value stores | [pykv](https://github.com/robcox2910/pykv) | [Docs](https://robcox2910.github.io/pykv/) | [fromscratch-pykv](https://pypi.org/project/fromscratch-pykv/) |
| PyDocDB | Document databases | [pydoc-db](https://github.com/robcox2910/pydoc-db) | [Docs](https://robcox2910.github.io/pydoc-db/) | [fromscratch-pydocdb](https://pypi.org/project/fromscratch-pydocdb/) |
| PyGraphDB | Graph databases | [pygraphdb](https://github.com/robcox2910/pygraphdb) | [Docs](https://robcox2910.github.io/pygraphdb/) | [fromscratch-pygraphdb](https://pypi.org/project/fromscratch-pygraphdb/) |
| **PyTSDB** | **Time-series databases** | [pytsdb](https://github.com/robcox2910/pytsdb) | [Docs](https://robcox2910.github.io/pytsdb/) | [fromscratch-pytsdb](https://pypi.org/project/fromscratch-pytsdb/) |
| PyVecDB | Vector databases | [pyvecdb](https://github.com/robcox2910/pyvecdb) | [Docs](https://robcox2910.github.io/pyvecdb/) | [fromscratch-pyvecdb](https://pypi.org/project/fromscratch-pyvecdb/) |
| PyColDB | Column-family databases | [pycoldb](https://github.com/robcox2910/pycoldb) | [Docs](https://robcox2910.github.io/pycoldb/) | [fromscratch-pycoldb](https://pypi.org/project/fromscratch-pycoldb/) |
| PyCrypt | Cryptography | [pycrypt](https://github.com/robcox2910/pycrypt) | [Docs](https://robcox2910.github.io/pycrypt/) | [fromscratch-pycrypt](https://pypi.org/project/fromscratch-pycrypt/) |
| PyNet | Computer networking | [pynet](https://github.com/robcox2910/pynet) | [Docs](https://robcox2910.github.io/pynet/) | [fromscratch-pynet](https://pypi.org/project/fromscratch-pynet/) |
| PyWeb | HTTP web servers | [pyweb](https://github.com/robcox2910/pyweb) | [Docs](https://robcox2910.github.io/pyweb/) | [fromscratch-pyweb](https://pypi.org/project/fromscratch-pyweb/) |
| PyGit | Version control | [pygit](https://github.com/robcox2910/pygit) | [Docs](https://robcox2910.github.io/pygit/) | [fromscratch-pygit](https://pypi.org/project/fromscratch-pygit/) |
| PySearch | Search engines | [pysearch](https://github.com/robcox2910/pysearch) | [Docs](https://robcox2910.github.io/pysearch/) | [fromscratch-pysearch](https://pypi.org/project/fromscratch-pysearch/) |
| PyMQ | Message queues | [pymq](https://github.com/robcox2910/pymq) | [Docs](https://robcox2910.github.io/pymq/) | [fromscratch-pymq](https://pypi.org/project/fromscratch-pymq/) |
| PyLLM | Language models (the brain) | [pyllm](https://github.com/robcox2910/pyllm) | [Docs](https://robcox2910.github.io/pyllm/) | [fromscratch-pyllm](https://pypi.org/project/fromscratch-pyllm/) |
| PyScheduler | Job scheduling | [pyscheduler](https://github.com/robcox2910/pyscheduler) | [Docs](https://robcox2910.github.io/pyscheduler/) | [fromscratch-pyscheduler](https://pypi.org/project/fromscratch-pyscheduler/) |
| PyStack | Full-stack integration | [pystack](https://github.com/robcox2910/pystack) | [Docs](https://robcox2910.github.io/pystack/) | [fromscratch-pystack](https://pypi.org/project/fromscratch-pystack/) |
<!-- series:end -->
