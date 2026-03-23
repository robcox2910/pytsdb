# Retention -- Throwing Away Last Year's Newspapers

## The Analogy

Every morning a newspaper lands on your doorstep. After a while, the pile gets huge! So you make a rule: **throw away any newspaper older than 7 days**.

A **retention policy** is the same idea for data points. You tell the database "keep data for 30 days" and it automatically discards anything older. This keeps your database from growing forever.

## In Code

```python
from datetime import timedelta
from pytsdb import TimeSeriesDB

db = TimeSeriesDB()
db.create_series("temperature")
# ... add lots of data over many days ...

# Keep only the last 7 days of data
db.set_retention("temperature", max_age=timedelta(days=7))

# Actually remove the old points
removed = db.apply_retention()
print(f"Removed {removed} expired points")
```

## Why Not Just Keep Everything?

1. **Storage**: A sensor recording every second generates 86,400 points per day. After a year, that's over 31 million points -- for just ONE sensor!
2. **Speed**: More data means slower queries.
3. **Relevance**: Do you really need the exact temperature at 3:42:17 AM from two years ago?

## Best Practice

Combine retention with downsampling:
1. Keep full-resolution data for the last week
2. Downsample to hourly and keep for a month
3. Downsample to daily and keep for a year
4. Delete anything older

This gives you the best of both worlds -- detailed recent data and long-term trends.
