"""Causal RSI/MFI and delayed pivot detection using only one-minute OHLCV."""
import math
from datetime import timedelta
from zoneinfo import ZoneInfo
from backtest import wilder_atr

ET = ZoneInfo('America/New_York')


def rsi_wilder(bars, period=14):
    out = [float('nan')] * len(bars)
    if len(bars) <= period: return out
    gains = [max(bars[i].c - bars[i-1].c, 0.) for i in range(1, len(bars))]
    losses = [max(bars[i-1].c - bars[i].c, 0.) for i in range(1, len(bars))]
    gain, loss = sum(gains[:period])/period, sum(losses[:period])/period
    def value(g,l): return 50. if g == 0 and l == 0 else (100. if l == 0 else 100.-100./(1.+g/l))
    out[period] = value(gain, loss)
    for i in range(period+1,len(bars)):
        gain = (gain*(period-1)+gains[i-1])/period
        loss = (loss*(period-1)+losses[i-1])/period
        out[i] = value(gain, loss)
    return out


def mfi(bars, period=14):
    out = [float('nan')] * len(bars)
    tp = [(b.h+b.l+b.c)/3 for b in bars]
    pos = [0.]*len(bars); neg = [0.]*len(bars)
    for i in range(1,len(bars)):
        flow = tp[i]*bars[i].v
        if tp[i] > tp[i-1]: pos[i] = flow
        elif tp[i] < tp[i-1]: neg[i] = flow
    for i in range(period,len(bars)):
        p,n = sum(pos[i-period+1:i+1]),sum(neg[i-period+1:i+1])
        out[i] = 50. if p+n == 0 else 100.*p/(p+n)
    return out


def confirmed_pivots(bars, side=1, k=3):
    """Return list of (pivot_index, first_known_index); side=+1 lows, -1 highs."""
    out=[]
    for p in range(k,len(bars)-k):
        v = bars[p].l if side==1 else -bars[p].h
        if all(v < (bars[p-j].l if side==1 else -bars[p-j].h) and
               v <= (bars[p+j].l if side==1 else -bars[p+j].h)
               for j in range(1,k+1)):
            out.append((p,p+k))
    return out


def previous_pivot(pivots,t,minimum=5,maximum=60):
    return next((p for p,known in reversed(pivots) if known <= t and minimum <= t-p <= maximum),None)


def continuity(bars,t,before=120,after=30):
    if t<before or t+after>=len(bars):return False
    return all(bars[j].start-bars[j-1].start == timedelta(minutes=1)
               for j in range(t-before+1,t+after+1))


def ny_window(b):
    et=(b.start+timedelta(minutes=1)).astimezone(ET)
    return et.weekday()<5 and 570<=et.hour*60+et.minute<=960


def trading_day(b):
    et=(b.start+timedelta(minutes=1)).astimezone(ET)
    return (et.date()+timedelta(days=1) if et.hour>=18 else et.date()).isoformat()


def ema(bars,n=50):
    out=[]; v=None; alpha=2/(n+1)
    for b in bars:
        v=b.c if v is None else v+alpha*(b.c-v)
        out.append(v)
    return out


def indicators(bars):
    return dict(atr=wilder_atr(bars),rsi=rsi_wilder(bars),mfi=mfi(bars),ema=ema(bars),
                lows=confirmed_pivots(bars,1),highs=confirmed_pivots(bars,-1))


def context_a(bars,ind,t,side):
    """Features are known by close(t); pivots only after confirmation."""
    piv=ind['lows'] if side==1 else ind['highs']
    p=previous_pivot(piv,t)
    a=max(ind['atr'][t-1],1e-12)
    base={'has_p1':int(p is not None),'price_diff_atr':math.nan,
          'rsi_diff_t':math.nan,'rsi_diff_t1':math.nan,'rsi_t':ind['rsi'][t],
          'rsi_p1':math.nan,'bars_since_p1':math.nan,'div_flag':0,
          'mfi_t':ind['mfi'][t],'mfi_diff_t':math.nan,'mfi_diff_t1':math.nan,
          'vol_ratio_t_p1':math.nan,'vol3_ratio_t_p1':math.nan}
    if p is None:return base
    pd=(bars[p].l-bars[t].l if side==1 else bars[t].h-bars[p].h)/a
    rd=side*(ind['rsi'][t]-ind['rsi'][p]);rd1=side*(ind['rsi'][t-1]-ind['rsi'][p])
    md=side*(ind['mfi'][t]-ind['mfi'][p]);md1=side*(ind['mfi'][t-1]-ind['mfi'][p])
    v0=sum(b.v for b in bars[t-2:t+1]);v1=sum(b.v for b in bars[p-1:p+2])
    base.update(price_diff_atr=pd,rsi_diff_t=rd,rsi_diff_t1=rd1,rsi_p1=ind['rsi'][p],
        bars_since_p1=t-p,div_flag=int(pd>=.25 and rd1>=2),mfi_diff_t=md,
        mfi_diff_t1=md1,vol_ratio_t_p1=bars[t].v/max(bars[p].v,1),
        vol3_ratio_t_p1=v0/max(v1,1))
    return base
