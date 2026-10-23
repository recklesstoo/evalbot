#!/usr/bin/env python3
"""EvalBot tester: replays ninjatrader/EvalBotAutoTrader.cs (V0.3) on 1-minute bars, with costs.

Research only; NO LIVE ORDERS. A simulation result is not evidence of profitability.
Input CSV columns: timestamp,open,high,low,close,volume (timestamp = bar START, ISO-8601).
"""
import argparse
import csv
import math
import random
import sys
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ONE_MIN = timedelta(minutes=1)
MIN_TRADES_WARN = 100


@dataclass
class Bar:
    start: datetime
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

    @property
    def end(self):
        """NinjaTrader stamps a bar with its CLOSE time; the CSV carries the start."""
        return self.start + ONE_MIN


@dataclass
class Params:
    """Same names and defaults as the .cs properties, plus cost and calendar settings."""
    risk_per_trade: float = 100.0
    daily_loss_limit: float = 400.0
    daily_profit_target: float = 750.0
    reward_risk: float = 2.0
    max_trades_per_day: int = 3
    max_contracts: int = 6
    sweep_lookback: int = 20
    atr_multiplier: float = 1.5
    atr_period: int = 14
    ema_period: int = 50
    min_stop_ticks: int = 8
    use_trend_filter: bool = True
    bars_required: int = 40
    session_start: int = 930
    session_end: int = 1130
    flatten_hhmm: int = 1659
    tick_size: float = 0.25
    point_value: float = 2.0
    commission_per_contract: float = 2.8     # round trip, USD per contract
    slippage_ticks: float = 1.0              # per slipped leg: market entry and stop/market exits
    chart_tz: str = "America/New_York"
    day_mode: str = "calendar"               # "calendar" = chart midnight (.cs); "cme" = 18:00 ET roll


@dataclass
class Trade:
    day: str
    side: int
    qty: int
    entry_idx: int
    exit_idx: int
    entry_time: datetime
    exit_time: datetime
    entry_price: float       # fill, after slippage
    exit_price: float        # fill, after slippage
    stop_ticks: int
    reason: str
    commission: float
    pnl_net: float
    r_gross: float           # (nominal exit - nominal entry) / stop, before any cost
    cost_r: float            # (commission + slipped legs * slippage * point value) / (stop * point value)
    r_net: float             # pnl_net / (stop * point value * qty) == r_gross - cost_r


@dataclass
class Result:
    trades: list
    skipped: dict
    n_bars: int


def parse_ts(text, tz):
    s = text.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def load_bars(path, input_tz="UTC"):
    """Read the CSV; bars are sorted, duplicates keep the last row, bad rows raise ValueError."""
    tz = timezone.utc if input_tz.upper() == "UTC" else ZoneInfo(input_tz)
    rows, dups = {}, 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: archivo vacio")
        cols = {name.strip().lower(): name for name in reader.fieldnames}
        missing = [c for c in ("timestamp", "open", "high", "low", "close") if c not in cols]
        if missing:
            raise ValueError(f"{path}: faltan columnas {missing}")
        for line, r in enumerate(reader, start=2):
            try:
                t = parse_ts(r[cols["timestamp"]], tz)
                o, h, l, c = (float(r[cols[k]]) for k in ("open", "high", "low", "close"))
                vol_raw = r[cols["volume"]] if "volume" in cols else ""
                v = float(vol_raw) if vol_raw not in ("", None) else 0.0
            except (ValueError, KeyError, TypeError) as e:
                raise ValueError(f"{path}:{line}: fila invalida ({e})") from None
            if not all(math.isfinite(x) for x in (o, h, l, c)) or h < max(o, c, l) or l > min(o, c, h):
                raise ValueError(f"{path}:{line}: OHLC inconsistente")
            if t in rows:
                dups += 1
            rows[t] = Bar(t, o, h, l, c, v)
    if not rows:
        raise ValueError(f"{path}: sin barras")
    if dups:
        print(f"AVISO: {dups} marcas de tiempo duplicadas; se conservo la ultima.", file=sys.stderr)
    return [rows[k] for k in sorted(rows)]


def wilder_atr(bars, period=14):
    """ATR as NinjaTrader computes it: Wilder smoothing, simple average while warming up."""
    out, prev = [], 0.0
    for i, b in enumerate(bars):
        if i == 0:
            val = b.h - b.l
        else:
            pc = bars[i - 1].c
            tr = max(b.h - b.l, abs(b.h - pc), abs(b.l - pc))
            val = (prev * i + tr) / (i + 1) if i + 1 < period else (prev * (period - 1) + tr) / period
        out.append(val)
        prev = val
    return out


def ema(values, period):
    k = 2.0 / (period + 1)
    out, prev = [], None
    for v in values:
        prev = v if prev is None else k * v + (1 - k) * prev
        out.append(prev)
    return out


def _in_session(hhmm, p):
    if p.session_start <= p.session_end:
        return p.session_start <= hhmm <= p.session_end
    return hhmm >= p.session_start or hhmm <= p.session_end


def simulate(bars, p):
    """Bar-close signal, entry at the next bar's open, one position at a time."""
    n = len(bars)
    tick, pv = p.tick_size, p.point_value
    slip = p.slippage_ticks * tick
    tz = ZoneInfo(p.chart_tz)
    atr = wilder_atr(bars, p.atr_period)
    trend = ema([b.c for b in bars], p.ema_period)
    min_i = max(p.bars_required, p.sweep_lookback + 2)

    trades, skipped = [], {"gap": 0, "size": 0}
    pos = pending = cur_day = None
    realized, trades_today, blocked = 0.0, 0, False

    def close_pos(i, nominal, reason, slipped):
        nonlocal pos, realized
        side, qty = pos["side"], pos["qty"]
        fill = nominal - side * slip if slipped else nominal
        stop_pts = pos["stop_ticks"] * tick
        commission = p.commission_per_contract * qty
        pnl = side * (fill - pos["fill"]) * pv * qty - commission
        legs = 2 if slipped else 1
        cost_r = (p.commission_per_contract + legs * slip * pv) / (stop_pts * pv)
        r_gross = side * (nominal - pos["nominal"]) / stop_pts
        trades.append(Trade(
            day=pos["day"], side=side, qty=qty, entry_idx=pos["entry_idx"], exit_idx=i,
            entry_time=bars[pos["entry_idx"]].start, exit_time=bars[i].start,
            entry_price=pos["fill"], exit_price=fill, stop_ticks=pos["stop_ticks"],
            reason=reason, commission=commission, pnl_net=pnl, r_gross=r_gross,
            cost_r=cost_r, r_net=pnl / (stop_pts * pv * qty)))
        realized += pnl
        pos = None

    for i, b in enumerate(bars):
        end_loc = b.end.astimezone(tz)
        start_loc = b.start.astimezone(tz)
        key = (end_loc + timedelta(hours=6) if p.day_mode == "cme" else end_loc).date()
        if key != cur_day:
            cur_day, realized, trades_today, blocked, pending = key, 0.0, 0, False, None

        if pending is not None:
            side, qty, stop_ticks, target_ticks, day = pending
            pending = None
            fill = b.o + side * slip
            pos = dict(side=side, qty=qty, stop_ticks=stop_ticks, fill=fill, nominal=b.o,
                       stop=fill - side * stop_ticks * tick, target=fill + side * target_ticks * tick,
                       entry_idx=i, entry_date=start_loc.date(), day=day, exit_flag=False)

        if pos is not None:
            hhmm_start = start_loc.hour * 100 + start_loc.minute
            reason = None
            if pos["exit_flag"]:
                reason = "DAILY_LIMIT"
            elif i > 0 and b.start - bars[i - 1].start != ONE_MIN:
                reason = "DATA_GAP"
            elif start_loc.date() != pos["entry_date"] or hhmm_start >= p.flatten_hhmm:
                reason = "FLATTEN"
            if reason:
                close_pos(i, b.o, reason, True)
            else:
                side = pos["side"]
                stop_hit = b.l <= pos["stop"] if side == 1 else b.h >= pos["stop"]
                target_hit = b.h >= pos["target"] if side == 1 else b.l <= pos["target"]
                if stop_hit:   # stop first when both fall in the same bar; gaps fill at the open
                    nominal = min(pos["stop"], b.o) if side == 1 else max(pos["stop"], b.o)
                    close_pos(i, nominal, "GAP_STOP" if nominal == b.o and nominal != pos["stop"] else "STOP", True)
                elif target_hit:
                    close_pos(i, pos["target"], "TARGET", False)

        if pos is not None:
            unrealized = pos["side"] * (b.c - pos["fill"]) * pv * pos["qty"]
        else:
            unrealized = 0.0
        total = realized + unrealized
        if total <= -p.daily_loss_limit or total >= p.daily_profit_target:
            blocked = True
            if pos is not None:
                pos["exit_flag"] = True

        if (blocked or i < min_i or pos is not None or pending is not None
                or trades_today >= p.max_trades_per_day
                or not _in_session(end_loc.hour * 100 + end_loc.minute, p)):
            continue

        window = bars[i - p.sweep_lookback:i]
        prior_low = min(x.l for x in window)
        prior_high = max(x.h for x in window)
        buy = b.l < prior_low - tick and b.c > prior_low and b.c > b.o
        sell = b.h > prior_high + tick and b.c < prior_high and b.c < b.o
        if buy == sell:
            continue
        if p.use_trend_filter and ((buy and b.c < trend[i]) or (sell and b.c > trend[i])):
            continue
        stop_pts = math.ceil(max(atr[i - 1] * p.atr_multiplier, p.min_stop_ticks * tick) / tick) * tick
        qty = min(p.max_contracts, math.floor(p.risk_per_trade / (stop_pts * pv)))
        if qty < 1:
            skipped["size"] += 1
            continue
        if i + 1 >= n or bars[i + 1].start - b.start != ONE_MIN:
            skipped["gap"] += 1
            continue
        stop_ticks = max(p.min_stop_ticks, round(stop_pts / tick))
        target_ticks = max(1, round(stop_ticks * p.reward_risk))
        pending = (1 if buy else -1, qty, stop_ticks, target_ticks, str(cur_day))
        trades_today += 1

    if pos is not None:
        close_pos(n - 1, bars[-1].c, "END_OF_DATA", True)
    return Result(trades, skipped, n)


def bootstrap_ci(trades, reps=2000, seed=12345):
    """95% CI of mean net R per trade, resampling whole trading days."""
    by_day = {}
    for t in trades:
        s, c = by_day.get(t.day, (0.0, 0))
        by_day[t.day] = (s + t.r_net, c + 1)
    days = list(by_day.values())
    k = len(days)
    if k < 2:
        return None
    rnd = random.Random(seed)
    means = []
    for _ in range(reps):
        tot = cnt = 0
        for _ in range(k):
            s, c = days[rnd.randrange(k)]
            tot += s
            cnt += c
        means.append(tot / cnt)
    means.sort()
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def summarize(trades, reps=2000):
    trades = sorted(trades, key=lambda t: t.exit_time)
    n = len(trades)
    s = dict(n=n, small_sample=n < MIN_TRADES_WARN, days=len({t.day for t in trades}))
    if n == 0:
        return s
    pnl = [t.pnl_net for t in trades]
    gains, losses = sum(x for x in pnl if x > 0), -sum(x for x in pnl if x < 0)
    equity = peak = max_dd = streak = worst = 0.0
    for x in pnl:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        streak = streak + 1 if x < 0 else 0
        worst = max(worst, streak)
    weeks = {}
    for t in trades:
        key = datetime.fromisoformat(t.day).isocalendar()[:2]
        weeks[key] = weeks.get(key, 0.0) + t.pnl_net
    s.update(
        wins=sum(1 for x in pnl if x > 0), win_rate=sum(1 for x in pnl if x > 0) / n,
        net=sum(pnl), commission=sum(t.commission for t in trades),
        expectancy_r=sum(t.r_net for t in trades) / n,
        mean_cost_r=sum(t.cost_r for t in trades) / n,
        profit_factor=(gains / losses) if losses else None,
        max_drawdown=max_dd, worst_losing_streak=int(worst),
        positive_weeks=sum(1 for v in weeks.values() if v > 0), weeks=len(weeks),
        ci_r=bootstrap_ci(trades, reps))
    return s


def print_summary(label, s):
    print(f"== {label}")
    print(f"operaciones: {s['n']}   dias con operaciones: {s['days']}")
    if s["n"] == 0:
        print("Sin operaciones.")
    else:
        ci = s["ci_r"]
        ci_text = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "n/d (menos de 2 dias)"
        pf = f"{s['profit_factor']:.2f}" if s["profit_factor"] is not None else "n/d"
        print(f"neto: {s['net']:+.2f} USD (comisiones {s['commission']:.2f})   win rate: {s['win_rate']:.1%}   PF: {pf}")
        print(f"expectativa neta: {s['expectancy_r']:+.3f} R/op   IC95% bootstrap por dias: {ci_text}   costo medio: {s['mean_cost_r']:.3f} R/op")
        print(f"max drawdown: {s['max_drawdown']:.2f} USD   peor racha perdedora: {s['worst_losing_streak']}   semanas positivas: {s['positive_weeks']}/{s['weeks']}")
    if s["small_sample"]:
        print(f"AVISO: n < {MIN_TRADES_WARN} operaciones. MUESTRA INSUFICIENTE: no sirve para elegir parametros ni filtros.")


VARIANTS = [
    ("base (replica del .cs)", {}),
    ("sin filtro EMA50", {"use_trend_filter": False}),
    ("barrido 10 barras", {"sweep_lookback": 10}),
    ("barrido 40 barras", {"sweep_lookback": 40}),
    ("stop ATR x1.0", {"atr_multiplier": 1.0}),
    ("stop ATR x2.0", {"atr_multiplier": 2.0}),
    ("objetivo 1.5R", {"reward_risk": 1.5}),
]


def apply_overrides(p, items):
    types = {f.name: f.type for f in fields(Params)}
    changes = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--set espera clave=valor, recibido: {item}")
        k, v = item.split("=", 1)
        if k not in types:
            raise SystemExit(f"Parametro desconocido: {k}. Validos: {', '.join(types)}")
        kind = types[k] if isinstance(types[k], type) else {"bool": bool, "int": int, "float": float, "str": str}[types[k]]
        changes[k] = (v.lower() in ("1", "true", "yes", "si")) if kind is bool else kind(v)
    return replace(p, **changes)


def write_trades(path, trades):
    cols = [f.name for f in fields(Trade)]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for t in sorted(trades, key=lambda t: t.entry_time):
            w.writerow([getattr(t, c).isoformat() if isinstance(getattr(t, c), datetime) else getattr(t, c) for c in cols])


def in_range(trades, start, end):
    return [t for t in trades if (not start or t.day >= start) and (not end or t.day <= end)]


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--start", help="primer dia de operaciones (YYYY-MM-DD)")
    ap.add_argument("--end", help="ultimo dia de operaciones (YYYY-MM-DD)")
    ap.add_argument("--input-tz", default="UTC", help="zona de timestamps sin offset (defecto UTC)")
    ap.add_argument("--set", action="append", default=[], metavar="clave=valor", help="sobrescribe un parametro de Params")
    ap.add_argument("--compare", action="store_true", help="prueba 7 variantes sobre los mismos datos")
    ap.add_argument("--trades-out", help="CSV con una fila por operacion")
    ap.add_argument("--boot-reps", type=int, default=2000)
    args = ap.parse_args(argv)

    params = apply_overrides(Params(), args.set)
    bars = load_bars(args.csv, args.input_tz)
    print(f"{len(bars)} barras  {bars[0].start:%Y-%m-%d} -> {bars[-1].start:%Y-%m-%d}  (UTC)")
    print("Solo investigacion: SIN ordenes reales. Una simulacion no prueba rentabilidad.")

    result = simulate(bars, params)
    trades = in_range(result.trades, args.start, args.end)
    print(f"senales descartadas: {result.skipped['gap']} por hueco de datos, {result.skipped['size']} por tamano < 1 contrato")
    print_summary("replica del .cs", summarize(trades, args.boot_reps))
    if args.trades_out:
        write_trades(args.trades_out, trades)
        print(f"operaciones escritas en {args.trades_out}")

    if args.compare:
        print("\nCOMPARACION DE VARIANTES (mismos datos). Con 7 variantes alguna sale 'ganadora' por azar:")
        print("elegir sobre un tramo y confirmar en otro que no se uso para elegir.")
        for name, change in VARIANTS:
            v_trades = in_range(simulate(bars, replace(params, **change)).trades, args.start, args.end)
            s = summarize(v_trades, args.boot_reps)
            if s["n"]:
                ci = s["ci_r"]
                ci_text = f"[{ci[0]:+.2f},{ci[1]:+.2f}]" if ci else "n/d"
                print(f"{name:26s} n={s['n']:4d}  neto={s['net']:+9.2f}  exp={s['expectancy_r']:+.3f}R  IC95={ci_text}")
            else:
                print(f"{name:26s} n=   0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
