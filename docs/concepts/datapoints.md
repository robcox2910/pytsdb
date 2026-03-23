# Data Points -- Thermometer Readings

## The Analogy

Every time you check a thermometer and write down the number, you're creating a **data point**. A data point is the smallest unit of information in a time-series database.

It has three parts:

1. **Timestamp** -- *When* did you look at the thermometer? (e.g. "July 4, 2024 at 2:00 PM")
2. **Value** -- *What* did it read? (e.g. 72.5°F)
3. **Tags** -- *Extra labels* that help you find it later (e.g. sensor="kitchen", floor="1")

## In Code

```python
from datetime import datetime, timezone
from pytsdb import DataPoint

reading = DataPoint(
    timestamp=datetime(2024, 7, 4, 14, 0, tzinfo=timezone.utc),
    value=72.5,
    tags={"sensor": "kitchen", "floor": "1"},
)

print(reading.value)       # 72.5
print(reading.tags)        # {'sensor': 'kitchen', 'floor': '1'}
```

## Why Are Tags Useful?

Imagine you have 10 temperature sensors around your house. Without tags, you'd need 10 separate series. With tags, you can store everything in one series and filter:

```python
# "Show me only the kitchen readings"
reading.matches_tags({"sensor": "kitchen"})  # True
reading.matches_tags({"sensor": "garage"})   # False
```

## Fun Fact

Data points in pytsdb are **frozen** (immutable) -- once created, you can't change them. This is like writing in pen instead of pencil. It keeps your data trustworthy!
