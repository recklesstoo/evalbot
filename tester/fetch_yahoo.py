#!/usr/bin/env python3
"""Download 1-minute MNQ=F bars from Yahoo and ACCUMULATE them in a CSV (timestamp = bar start, UTC).

Yahoo serves only the last ~30 days of 1-minute data, in windows of at most 7 days, so run this
regularly. The continuous series is Yahoo's own: rollover handling and volume are not verified.
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def read_existing(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["timestamp"]: r for r in csv.DictReader(f)}


def fetch(symbol, days):
    import yfinance as yf          # imported here so the module stays importable without network deps
    rows = {}
    end = datetime.now(timezone.utc)
    start_limit = end - timedelta(days=days)
    while end > start_limit:
        start = max(start_limit, end - timedelta(days=7))
        df = yf.Ticker(symbol).history(start=start, end=end, interval="1m", auto_adjust=False)
        for ts, r in df.iterrows():
            if any(v != v for v in (r["Open"], r["High"], r["Low"], r["Close"])):
                continue
            key = ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
            rows[key] = dict(timestamp=key, open=r["Open"], high=r["High"], low=r["Low"],
                             close=r["Close"], volume=r["Volume"])
        end = start
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", default="MNQ=F")
    ap.add_argument("--days", type=int, default=29, help="ventana hacia atras (Yahoo permite ~30)")
    ap.add_argument("--out", default="data/MNQ_1m.csv")
    args = ap.parse_args(argv)
    out = Path(args.out)
    merged = read_existing(out)
    before = len(merged)
    merged.update(fetch(args.symbol, args.days))
    if not merged:
        print("Yahoo no devolvio barras; no se escribio nada.", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for key in sorted(merged):
            w.writerow(merged[key])
    print(f"{out}: {len(merged)} barras ({len(merged) - before} nuevas)  {min(merged)} -> {max(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
