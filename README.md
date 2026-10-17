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

<!-- docs:start -->
## Documentation

Full docs (with kid-friendly explanations of every idea): https://robcox2910.github.io/pytsdb/
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

Other projects in the series ([PyStack](https://github.com/robcox2910/pystack)) use a pinned release of this one,
not whatever is on `main`. To publish a change for them:

1. Merge the change to `main`.
2. Tag it: `git tag -a vX.Y.Z -m vX.Y.Z && git push origin vX.Y.Z`.
   A change to the public API bumps the minor version (`v0.1.0` → `v0.2.0`);
   anything else bumps the patch (`v0.1.0` → `v0.1.1`).
3. In each project that uses it, edit the tag in `[tool.uv.sources]`, run
   `uv lock --upgrade-package <name>`, and open a pull request so CI checks
   the pair together.

<!-- series:start -->
## Related Projects

This project is one of a series that builds real systems "from scratch in Python" to teach how they work. See the [series home](https://robcox2910.github.io/) for the full story.

| Project | What it teaches | Repository | Docs |
| --- | --- | --- | --- |
| PyOS | Operating systems | [py-os](https://github.com/robcox2910/py-os) | [Docs](https://robcox2910.github.io/py-os/) |
| Pebble | Compilers and programming languages | [pebble-lang](https://github.com/robcox2910/pebble-lang) | [Docs](https://robcox2910.github.io/pebble-lang/) |
| PyDB | Relational databases | [pydb](https://github.com/robcox2910/pydb) | [Docs](https://robcox2910.github.io/pydb/) |
| PyKV | Key-value stores | [pykv](https://github.com/robcox2910/pykv) | [Docs](https://robcox2910.github.io/pykv/) |
| PyDocDB | Document databases | [pydoc-db](https://github.com/robcox2910/pydoc-db) | [Docs](https://robcox2910.github.io/pydoc-db/) |
| PyGraphDB | Graph databases | [pygraphdb](https://github.com/robcox2910/pygraphdb) | [Docs](https://robcox2910.github.io/pygraphdb/) |
| **PyTSDB** | **Time-series databases** | [pytsdb](https://github.com/robcox2910/pytsdb) | [Docs](https://robcox2910.github.io/pytsdb/) |
| PyVecDB | Vector databases | [pyvecdb](https://github.com/robcox2910/pyvecdb) | [Docs](https://robcox2910.github.io/pyvecdb/) |
| PyColDB | Column-family databases | [pycoldb](https://github.com/robcox2910/pycoldb) | [Docs](https://robcox2910.github.io/pycoldb/) |
| PyCrypt | Cryptography | [pycrypt](https://github.com/robcox2910/pycrypt) | [Docs](https://robcox2910.github.io/pycrypt/) |
| PyNet | Computer networking | [pynet](https://github.com/robcox2910/pynet) | [Docs](https://robcox2910.github.io/pynet/) |
| PyWeb | HTTP web servers | [pyweb](https://github.com/robcox2910/pyweb) | [Docs](https://robcox2910.github.io/pyweb/) |
| PyGit | Version control | [pygit](https://github.com/robcox2910/pygit) | [Docs](https://robcox2910.github.io/pygit/) |
| PySearch | Search engines | [pysearch](https://github.com/robcox2910/pysearch) | [Docs](https://robcox2910.github.io/pysearch/) |
| PyMQ | Message queues | [pymq](https://github.com/robcox2910/pymq) | [Docs](https://robcox2910.github.io/pymq/) |
| PyLLM | Language models (the brain) | [pyllm](https://github.com/robcox2910/pyllm) | [Docs](https://robcox2910.github.io/pyllm/) |
| PyStack | Full-stack integration | [pystack](https://github.com/robcox2910/pystack) | [Docs](https://robcox2910.github.io/pystack/) |
<!-- series:end -->
