# ---- Step 1: clean 1m data and build 5m candles, NY 09:00-10:30 session ----
# Input : DELTA_BTCUSD_1m_0900-1030_NY_ema5.csv  (1m, 09:00-10:29 NY, ema5_close already warm from 24h data)
#         DELTA_BTCUSD_5m_0900-1000_NY_ema5.csv  (5m, 09:00-09:55 NY, used only to seed the 5m EMA5)
# Output: clean/BTCUSD_1m_0900-1030_clean.csv, clean/BTCUSD_5m_0900-1030_clean.csv, clean/day_report.csv
import os
import pandas as pd

DATA_DIR = "/mnt/project-files/"        # in Colab: folder holding the CSVs, e.g. "/content/drive/MyDrive/BTC_ema/"
OUT_DIR  = os.path.join(DATA_DIR, "clean")
N_1M, N_5M = 90, 18                     # 09:00..10:29 (1m) and 09:00..10:25 (5m); the source has no 10:30 candle
FROZEN_RUN = 10                         # >= 10 consecutive flat, zero-volume 1m candles = feed outage -> drop day
ALPHA = 2 / (5 + 1)                     # EMA5, same as source: ema = a*close + (1-a)*prev, no reset per day

m1 = pd.read_csv(DATA_DIR + "DELTA_BTCUSD_1m_0900-1030_NY_ema5.csv", parse_dates=["datetime_ny", "datetime_utc"])
m5_src = pd.read_csv(DATA_DIR + "DELTA_BTCUSD_5m_0900-1000_NY_ema5.csv", parse_dates=["datetime_ny"])
m1 = m1.sort_values("datetime_ny").drop_duplicates("datetime_ny").reset_index(drop=True)
m1["date"] = m1["datetime_ny"].dt.date

# ---- per-day checks on 1m ----
def longest_frozen_run(g):
    frozen = (g["high"] == g["low"]) & (g["volume"] == 0)
    runs = frozen.groupby((~frozen).cumsum()).sum()
    return int(runs.max()) if len(runs) else 0

all_days = pd.date_range(m5_src["datetime_ny"].min().date(), m1["datetime_ny"].max().date()).date
rep = m1.groupby("date").agg(candles=("close", "size"), volume=("volume", "sum"),
                             zero_vol_candles=("volume", lambda v: int((v == 0).sum())))
rep["longest_frozen_run"] = m1.groupby("date").apply(longest_frozen_run)
rep = rep.reindex(all_days)
rep.index.name = "date"
rep["candles"] = rep["candles"].fillna(0).astype(int)

def reason(r):
    if r.candles == 0:                        return "missing from 1m file"
    if r.candles != N_1M:                     return f"incomplete ({r.candles}/{N_1M} candles)"
    if r.volume == 0:                         return "flat, zero volume"
    if r.zero_vol_candles > N_1M / 2:         return f"dead market ({int(r.zero_vol_candles)} zero-volume candles)"
    if r.longest_frozen_run >= FROZEN_RUN:    return f"feed outage ({int(r.longest_frozen_run)} frozen candles in a row)"
    return ""
rep["drop_reason"] = rep.apply(reason, axis=1)
rep["kept"] = rep["drop_reason"] == ""
keep = set(rep.index[rep["kept"]])

clean1 = m1[m1["date"].isin(keep)].drop(columns="date").reset_index(drop=True)

# ---- 5m candles from 1m (whole 09:00-10:25 per day) ----
x = m1[m1["date"].isin(keep)].copy()
x["bucket"] = x["datetime_ny"].dt.floor("5min")
c5 = x.groupby("bucket").agg(tz=("tz", "first"), datetime_utc=("datetime_utc", "first"),
                             open=("open", "first"), high=("high", "max"), low=("low", "min"),
                             close=("close", "last"), volume=("volume", "sum"), n=("close", "size"))
c5 = c5.rename_axis("datetime_ny").reset_index()
assert (c5["n"] == 5).all(), "a 5m bucket does not have 5 one-minute candles"
c5["date"] = c5["datetime_ny"].dt.date

# EMA5 on 5m closes. The source 5m EMA is continuous over 24h data, so the 09:00 value carries the
# overnight history. Seed each day from the source 09:00 EMA, then roll forward on our 5m closes.
# That reproduces the source exactly for 09:00-09:55 and extends it correctly to 10:25.
first = m5_src[m5_src["datetime_ny"].dt.strftime("%H:%M") == "09:00"]
seed = pd.Series(first["ema5_close"].values, index=first["datetime_ny"].dt.date)
def day_ema(g):
    ema, out = seed[g.name], []
    for i, c in enumerate(g["close"]):
        ema = ema if i == 0 else ALPHA * c + (1 - ALPHA) * ema
        out.append(round(ema, 2))
    return pd.Series(out, index=g.index)
c5["ema5_close"] = c5.groupby("date", group_keys=False).apply(day_ema)

chk = c5.merge(m5_src[["datetime_ny", "ema5_close"]], on="datetime_ny", suffixes=("", "_src"))
print(f"5m EMA check vs source 5m file (09:00-09:55): max diff {(chk.ema5_close - chk.ema5_close_src).abs().max():.3f}")
bad5 = c5.groupby("date").size()
assert (bad5 == N_5M).all(), "a day does not have 18 five-minute candles"
clean5 = c5[["datetime_ny", "tz", "datetime_utc", "open", "high", "low", "close", "volume", "ema5_close"]]

# ---- save ----
os.makedirs(OUT_DIR, exist_ok=True)
fmt = lambda d: d.assign(datetime_ny=d.datetime_ny.dt.strftime("%Y-%m-%d %H:%M:%S"),
                         datetime_utc=d.datetime_utc.dt.strftime("%Y-%m-%d %H:%M:%S"))
fmt(clean1).to_csv(os.path.join(OUT_DIR, "BTCUSD_1m_0900-1030_clean.csv"), index=False)
fmt(clean5).to_csv(os.path.join(OUT_DIR, "BTCUSD_5m_0900-1030_clean.csv"), index=False)
rep.to_csv(os.path.join(OUT_DIR, "day_report.csv"))

dropped = rep[~rep["kept"]]
print(f"Calendar days {len(rep)}: kept {len(keep)}, dropped {len(dropped)}")
print(f"1m rows {len(clean1)} ({len(keep)} x {N_1M}), 5m rows {len(clean5)} ({len(keep)} x {N_5M})")
print(dropped[["candles", "volume", "zero_vol_candles", "longest_frozen_run", "drop_reason"]].to_string())
