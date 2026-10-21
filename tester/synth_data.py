#!/usr/bin/env python3
"""Synthetic 1-minute bars for tester smoke checks only, not market data."""
import argparse, csv, random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")

def market_open(t_utc):
    et=t_utc.astimezone(ET)
    wd=et.weekday()
    return not (wd==5 or (wd==4 and et.hour>=17) or (wd==6 and et.hour<18) or et.hour==17)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=60)
    ap.add_argument("--seed",type=int,default=7)
    ap.add_argument("--out",default="data/synthetic_1m.csv")
    a=ap.parse_args()
    rnd=random.Random(a.seed)
    t=datetime(2026,8,3,tzinfo=timezone.utc)
    end=t+timedelta(days=a.days)
    px,vol=20000.0,2.0
    q=lambda x:round(x*4)/4
    from pathlib import Path
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    with open(a.out,"w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["timestamp","open","high","low","close","volume"])
        while t<end:
            if market_open(t):
                vol=max(.8,min(8.,vol*.97+.03*2.5+abs(rnd.gauss(0,.25))))
                o=px;c=q(o+rnd.gauss(0,vol))
                h=q(max(o,c)+abs(rnd.gauss(0,vol*.6)))
                l=q(min(o,c)-abs(rnd.gauss(0,vol*.6)))
                w.writerow([t.strftime("%Y-%m-%dT%H:%M:%SZ"),o,h,l,c,rnd.randint(50,900)])
                px=c
            t+=timedelta(minutes=1)
    print("escrito",a.out)
if __name__=="__main__":main()
