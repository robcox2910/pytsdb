# What is a Time-Series Database?

## The Weather Station Logbook

Imagine you run a weather station in your backyard. Every hour, you walk outside with a thermometer, read the temperature, and write it down in a logbook:

| Time        | Temperature |
|-------------|-------------|
| 8:00 AM     | 65°F        |
| 9:00 AM     | 68°F        |
| 10:00 AM    | 72°F        |
| 11:00 AM    | 75°F        |

That logbook **is** a time-series database! Each row has:
- **When** you took the reading (the *timestamp*)
- **What** the reading was (the *value*)

A time-series database is just a really smart logbook that can:
- Store millions of readings without getting slow
- Answer questions like "What was the hottest day last week?"
- Automatically throw away readings older than a year

## Why Does This Matter?

Time-series data is *everywhere*:
- **Fitness trackers** record your heart rate every second
- **Stock markets** track prices every millisecond
- **Weather apps** store temperature, humidity, and wind speed
- **Video games** log player scores over time
- **Servers** monitor CPU usage, memory, and network traffic

Regular databases (like the ones that store your user profile) aren't great at handling millions of timestamped readings. That's why engineers built specialised tools like InfluxDB, Prometheus, and TimescaleDB.

**pytsdb** is a tiny version of those tools, built from scratch in Python so you can learn how they work!

## What You'll Learn

By exploring pytsdb you'll understand:
1. How data points are stored in sorted order (binary search!)
2. How time-range queries work efficiently
3. How aggregation turns thousands of readings into useful summaries
4. How downsampling reduces data without losing the big picture
5. How retention policies keep your database from growing forever
6. How to save and load data with JSON serialization

Ready? Head over to the [concepts](concepts/) folder to dive deeper!
