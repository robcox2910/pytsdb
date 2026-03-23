# Queries -- Checking Yesterday's Weather

## The Analogy

Imagine flipping through your logbook and saying:
> "Show me all the readings from **yesterday** where the **sensor was in the kitchen**."

That's a query! You're narrowing down your data by:
1. **Time range** -- only yesterday (a start time and an end time)
2. **Tags** -- only the kitchen sensor

## In Code

```python
from datetime import datetime, timezone
from pytsdb import TimeSeriesDB

db = TimeSeriesDB()
db.create_series("temp")

db.add_point("temp", value=68.0,
             timestamp=datetime(2024, 7, 4, 8, 0, tzinfo=timezone.utc),
             tags={"sensor": "kitchen"})
db.add_point("temp", value=71.0,
             timestamp=datetime(2024, 7, 4, 10, 0, tzinfo=timezone.utc),
             tags={"sensor": "bedroom"})
db.add_point("temp", value=75.0,
             timestamp=datetime(2024, 7, 4, 12, 0, tzinfo=timezone.utc),
             tags={"sensor": "kitchen"})

# Time range only
morning = db.query("temp",
                   start=datetime(2024, 7, 4, 7, 0, tzinfo=timezone.utc),
                   end=datetime(2024, 7, 4, 11, 0, tzinfo=timezone.utc))
print(len(morning))  # 2

# Time range + tag filter
kitchen_morning = db.query("temp",
                           start=datetime(2024, 7, 4, 7, 0, tzinfo=timezone.utc),
                           end=datetime(2024, 7, 4, 11, 0, tzinfo=timezone.utc),
                           tags={"sensor": "kitchen"})
print(len(kitchen_morning))  # 1
```

## How It Works Under the Hood

1. **Binary search** finds the first and last points in the time range (fast!)
2. **Tag filtering** scans only those points and keeps the ones whose tags match

This two-step approach means we never waste time scanning points that are outside our time window.
