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

## Documentation

See the [docs/](docs/) folder for kid-friendly explanations with real-world analogies:

- [What is a Time-Series DB?](docs/index.md) -- weather station logbook analogy
- [Data Points](docs/concepts/datapoints.md) -- thermometer readings
- [Time Series](docs/concepts/series.md) -- a week of readings
- [Queries](docs/concepts/queries.md) -- checking yesterday's weather
- [Aggregation](docs/concepts/aggregation.md) -- weekly average temperature
- [Downsampling](docs/concepts/downsampling.md) -- monthly summaries
- [Retention](docs/concepts/retention.md) -- throwing away old newspapers

## Development

```bash
uv sync --all-extras
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run pyright src tests
uv run pytest
```

## Related Projects

| Project | Description |
|---------|-------------|
| [py-os](https://github.com/robcox2910/py-os) | Educational operating system concepts |
| [pebble-lang](https://github.com/robcox2910/pebble-lang) | A tiny programming language |
| [pydb](https://github.com/robcox2910/pydb) | Educational relational database engine |
| [pyweb](https://github.com/robcox2910/pyweb) | Educational web framework |
| [pygit](https://github.com/robcox2910/pygit) | Educational Git implementation |
| [pycrypt](https://github.com/robcox2910/pycrypt) | Educational cryptography library |
| [pynet](https://github.com/robcox2910/pynet) | Educational networking library |
| [pysearch](https://github.com/robcox2910/pysearch) | Educational search engine |
| [pymq](https://github.com/robcox2910/pymq) | Educational message queue |
| [pykv](https://github.com/robcox2910/pykv) | Educational key-value store |
| [pydocdb](https://github.com/robcox2910/pydocdb) | Educational document database |
| [pygraphdb](https://github.com/robcox2910/pygraphdb) | Educational graph database |
| [pystack](https://github.com/robcox2910/pystack) | Unified platform integrating all projects |
