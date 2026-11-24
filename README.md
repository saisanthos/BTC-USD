# BTC-USD

Intraday BTC/USD candle data for the New York morning session, with a 5-period EMA of the close.

## Files

| File | Interval | Session (NY time) | Rows |
|---|---|---|---|
| `DELTA_BTCUSD_1m_0900-1000_NY_ema5.csv` | 1 minute | 09:00–10:00 | 62,280 |
| `DELTA_BTCUSD_1m_0900-1030_NY_ema5.csv` | 1 minute | 09:00–10:30 | 93,420 |
| `DELTA_BTCUSD_5m_0900-1000_NY_ema5.csv` | 5 minutes | 09:00–10:00 | 12,576 |

Coverage: 2024-01-10 to 2026-11-22. The `DELTA_` prefix suggests the data comes from Delta Exchange.

## Columns

| Column | Description |
|---|---|
| `datetime_ny` | Bar start time in New York local time |
| `tz` | `EST` or `EDT`, the offset in effect for that bar |
| `datetime_utc` | Bar start time in UTC |
| `open`, `high`, `low`, `close` | Bar prices in USD |
| `volume` | Traded volume for the bar |
| `ema5_close` | 5-period exponential moving average of `close` |

## Known data notes

- The 1-minute files are missing 10 days that the 5-minute file has: 2024-01-11 to 01-15, 01-18, 01-20 to 01-22 and 01-28.
- Some bars have zero volume or flat OHLC (open = high = low = close). These may be placeholders for periods with no trades.
- The 09:00–10:00 1-minute file is a subset of the 09:00–10:30 one.
- `volume` is written as `0.0` in two files and `0` in the third.

## Usage

```python
import pandas as pd

df = pd.read_csv(
    "DELTA_BTCUSD_5m_0900-1000_NY_ema5.csv",
    parse_dates=["datetime_ny", "datetime_utc"],
)
```
