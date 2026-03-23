# Downsampling -- Monthly Summaries

## The Analogy

Imagine you've been writing in your diary every single minute for a year. That's over half a million entries! You don't need minute-by-minute detail from six months ago -- a daily summary would be fine.

**Downsampling** is like rewriting your diary at a lower resolution:
- Minute data becomes hourly averages
- Hourly data becomes daily averages
- Daily data becomes weekly averages

You lose the tiny details but keep the big picture -- and save a ton of space!

## In Code

```python
from datetime import timedelta
from pytsdb import TimeSeriesDB, AggFunc

db = TimeSeriesDB()
db.create_series("cpu")
# ... add per-minute CPU readings ...

# Convert minute readings to hourly averages
hourly = db.downsample("cpu", target_interval=timedelta(hours=1))

# Convert to daily maximums
daily_peaks = db.downsample("cpu", target_interval=timedelta(days=1), func=AggFunc.MAX)
```

## When to Downsample

- **Recent data**: Keep full resolution (every second or minute)
- **Last month**: Downsample to hourly
- **Last year**: Downsample to daily
- **Older than a year**: Maybe just keep weekly summaries

This is exactly how real monitoring systems like Prometheus and Grafana handle long-term storage!

## Downsampling vs Aggregation

They're closely related! Downsampling *is* aggregation -- it just emphasises the idea of **reducing resolution** rather than answering a one-off question. Under the hood, pytsdb uses the same aggregation engine for both.
