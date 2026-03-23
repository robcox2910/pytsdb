"""pytsdb -- an educational time-series database.

A time-series database stores data points that each have a **timestamp**,
a **value**, and optional **tags**.  Think of it like a weather station's
logbook: every few minutes you jot down the temperature, humidity, and
wind speed along with the current time.

Quick start::

    from pytsdb import TimeSeriesDB

    db = TimeSeriesDB()
    db.create_series("temperature")
    db.add_point("temperature", value=72.5, tags={"sensor": "kitchen"})

    points = db.query("temperature")
    print(points)

Modules:
    datapoint    -- A single timestamped reading.
    series       -- An ordered collection of readings for one metric.
    database     -- A container that manages multiple series.
    query        -- Time-range and tag-based lookups.
    aggregation  -- Windowed summaries (avg, min, max, sum, count).
    downsampling -- Resolution reduction (e.g. minutes to hours).
    retention    -- Auto-expiry of old data.
    persistence  -- Save / load the database to JSON files.
    errors       -- Custom exception classes.
"""

from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.database import TimeSeriesDB
from pytsdb.datapoint import DataPoint
from pytsdb.downsampling import downsample
from pytsdb.errors import (
    DuplicateSeriesError,
    EmptySeriesError,
    InvalidRetentionError,
    InvalidWindowError,
    PyTSDBError,
    SeriesNotFoundError,
)
from pytsdb.persistence import load, save
from pytsdb.query import filter_by_tags, query, query_range
from pytsdb.retention import RetentionPolicy
from pytsdb.series import TimeSeries

__all__ = [
    "AggFunc",
    "DataPoint",
    "DuplicateSeriesError",
    "EmptySeriesError",
    "InvalidRetentionError",
    "InvalidWindowError",
    "PyTSDBError",
    "RetentionPolicy",
    "SeriesNotFoundError",
    "TimeSeries",
    "TimeSeriesDB",
    "aggregate",
    "downsample",
    "filter_by_tags",
    "load",
    "query",
    "query_range",
    "save",
]
