# Time Series -- A Week of Readings

## The Analogy

If a data point is one thermometer reading, a **time series** is an entire page in your logbook -- a whole week (or month, or year!) of readings for one thing you're measuring.

The series has a **name** (like "kitchen_temperature") and keeps all its data points sorted by time, oldest first. It's like keeping your diary entries in date order so you can quickly flip to any day.

## In Code

```python
from datetime import datetime, timezone
from pytsdb import TimeSeries

series = TimeSeries("temperature")

series.add_value(68.0, timestamp=datetime(2024, 7, 4, 8, 0, tzinfo=timezone.utc))
series.add_value(72.5, timestamp=datetime(2024, 7, 4, 10, 0, tzinfo=timezone.utc))
series.add_value(75.0, timestamp=datetime(2024, 7, 4, 12, 0, tzinfo=timezone.utc))

print(len(series))         # 3
print(series.first.value)  # 68.0 (earliest reading)
print(series.last.value)   # 75.0 (latest reading)
```

## Why Sorted Order Matters

When points are sorted, finding "all readings between 9 AM and 11 AM" is super fast. Instead of checking every single point, we can use **binary search** -- the same trick you use when looking up a word in a dictionary. You open to the middle, see if your word comes before or after, and keep halving until you find it.

This makes queries run in O(log n) time instead of O(n). For a million points, that's roughly 20 steps instead of 1,000,000!
