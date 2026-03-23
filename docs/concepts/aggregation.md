# Aggregation -- Weekly Average Temperature

## The Analogy

You recorded the temperature every hour for a whole week. That's 168 readings! Your teacher asks: "What was the average temperature each day?"

Instead of reading all 168 numbers, you:
1. **Group** them by day (7 groups of 24 readings)
2. **Summarise** each group (add them up and divide by 24)

That's aggregation! You pick a **window** (one day) and a **function** (average) and let the computer crunch the numbers.

## Available Functions

| Function | What it does                  | Example                          |
|----------|-------------------------------|----------------------------------|
| AVG      | Average of all values         | "Average temperature this hour"  |
| MIN      | Smallest value                | "Coldest reading today"          |
| MAX      | Largest value                 | "Hottest reading today"          |
| SUM      | Total of all values           | "Total rainfall this week"       |
| COUNT    | Number of readings            | "How many readings per hour?"    |

## In Code

```python
from datetime import timedelta
from pytsdb import TimeSeriesDB, AggFunc

db = TimeSeriesDB()
db.create_series("temp")
# ... add hourly readings ...

# Get the average temperature per hour
hourly_avg = db.aggregate("temp", window=timedelta(hours=1), func=AggFunc.AVG)

# Get the max temperature per day
daily_max = db.aggregate("temp", window=timedelta(days=1), func=AggFunc.MAX)
```

## How Time Buckets Work

Every data point's timestamp is mapped to a **bucket**. For a 1-hour window, all points between 10:00 and 10:59 go into the "10:00" bucket. The function is then applied to each bucket independently.
