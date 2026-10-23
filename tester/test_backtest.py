"""Known-outcome scenarios for backtest.py. Hand-built bars, never market data.

Flat warm-up: price 20000, high/low +-1 -> TR = 2, ATR = 2, stop = ceil(1.5*2/.25)*.25 = 3.0 (12 ticks),
target = 24 ticks, qty = min(6, floor(100 / (3.0*2))) = 6. With 1 tick of slippage on the entry the long fill
is 20000.75 (open 20000.5), so stop 19997.75 and target 20006.75. Commission 2.80 x 6 = 16.80.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import backtest as bt
from backtest import Bar, Params, simulate, summarize, wilder_atr, load_bars

HERE = os.path.dirname(os.path.abspath(__file__))
T0 = datetime(2026, 3, 2, 13, 0, tzinfo=timezone.utc)      # 08:00 ET (EST)
LONG_SIGNAL = (19999.5, 20001.0, 19998.0, 20000.5)
SHORT_SIGNAL = (20000.5, 20002.0, 19999.5, 19999.5)
RISK_PER_STOP_USD = 3.0 * 2.0 * 6                           # stop points * point value * qty


class Builder:
    def __init__(self, start=T0):
        self.t, self.bars = start, []

    def bar(self, o, h, l, c, v=100):
        self.bars.append(Bar(self.t, o, h, l, c, v))
        self.t += timedelta(minutes=1)
        return len(self.bars) - 1

    def flat(self, n, price=20000.0, half=1.0):
        for _ in range(n):
            self.bar(price, price + half, price - half, price)

    def skip(self, minutes):
        self.t += timedelta(minutes=minutes)


def scenario(signal, *after, params=None, warmup=120):
    b = Builder()
    b.flat(warmup)
    b.bar(*signal)
    for bar in after:
        b.bar(*bar)
    return simulate(b.bars, params or Params())


def only_trade(test, result):
    test.assertEqual(len(result.trades), 1)
    return result.trades[0]


class ScenarioTests(unittest.TestCase):
    def test_long_target(self):
        t = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0)))
        self.assertEqual((t.side, t.qty, t.reason, t.stop_ticks), (1, 6, "TARGET", 12))
        self.assertAlmostEqual(t.entry_price, 20000.75)
        self.assertAlmostEqual(t.exit_price, 20006.75)             # target fills without slippage
        self.assertAlmostEqual(t.pnl_net, 6.0 * 2 * 6 - 16.8)      # 55.20
        self.assertAlmostEqual(t.r_net, 55.2 / RISK_PER_STOP_USD)

    def test_long_stop(self):
        t = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20001.0, 19997.0, 19998.0)))
        self.assertEqual(t.reason, "STOP")
        self.assertAlmostEqual(t.exit_price, 19997.5)              # stop 19997.75 minus 1 tick
        self.assertAlmostEqual(t.pnl_net, -3.25 * 12 - 16.8)       # -55.80

    def test_same_bar_stop_wins(self):
        t = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20007.0, 19997.0, 20000.0)))
        self.assertEqual(t.reason, "STOP")
        self.assertLess(t.pnl_net, 0)

    def test_gap_through_stop_fills_at_open(self):
        t = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20001.0, 20000.0, 20000.5),
                                      (19990.0, 19991.0, 19989.0, 19990.0)))
        self.assertEqual(t.reason, "GAP_STOP")
        self.assertAlmostEqual(t.exit_price, 19989.75)             # open 19990 minus 1 tick
        self.assertAlmostEqual(t.pnl_net, -11.0 * 12 - 16.8)       # -148.80
        self.assertLess(t.r_net, -1.0)

    def test_short_target_and_stop(self):
        t = only_trade(self, scenario(SHORT_SIGNAL, (19999.5, 19999.75, 19993.0, 19994.0)))
        self.assertEqual((t.side, t.reason), (-1, "TARGET"))
        self.assertAlmostEqual(t.entry_price, 19999.25)
        self.assertAlmostEqual(t.exit_price, 19993.25)
        self.assertAlmostEqual(t.pnl_net, 6.0 * 12 - 16.8)
        t = only_trade(self, scenario(SHORT_SIGNAL, (19999.5, 20003.0, 19999.0, 20002.0)))
        self.assertEqual(t.reason, "STOP")                          # stop 20002.25, fill 20002.5
        self.assertAlmostEqual(t.pnl_net, -3.25 * 12 - 16.8)

    def test_daily_loss_limit_exits_next_open_and_blocks(self):
        r = scenario(LONG_SIGNAL, (20000.5, 20001.0, 19998.0, 19998.25), (19998.0, 19998.5, 19997.9, 19998.0),
                     params=Params(daily_loss_limit=25))
        t = only_trade(self, r)
        self.assertEqual(t.reason, "DAILY_LIMIT")
        self.assertAlmostEqual(t.exit_price, 19997.75)
        self.assertAlmostEqual(t.pnl_net, -3.0 * 12 - 16.8)

    def test_daily_profit_target_blocks_new_entries(self):
        b = Builder()
        b.flat(120)
        b.bar(*LONG_SIGNAL)
        b.bar(20000.5, 20007.0, 20000.0, 20006.0)                   # +55.20
        b.flat(22, price=20006.0)
        b.bar(20005.5, 20007.0, 20004.0, 20006.5)
        b.bar(20006.5, 20007.0, 20006.0, 20006.5)
        self.assertEqual(len(simulate(b.bars, Params()).trades), 2)
        self.assertEqual(len(simulate(b.bars, Params(daily_profit_target=50)).trades), 1)

    def test_max_trades_per_day(self):
        b = Builder()
        b.flat(120)
        b.bar(*LONG_SIGNAL)
        b.bar(20000.5, 20007.0, 20000.0, 20006.0)
        b.flat(22, price=20006.0)
        b.bar(20005.5, 20007.0, 20004.0, 20006.5)
        b.bar(20006.5, 20007.0, 20006.0, 20006.5)
        self.assertEqual(len(simulate(b.bars, Params(max_trades_per_day=1)).trades), 1)
        self.assertEqual(len(simulate(b.bars, Params(max_trades_per_day=3)).trades), 2)

    def test_signal_outside_session_is_ignored(self):
        b = Builder(datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))
        b.flat(120)                                                  # now 17:00Z = 12:00 ET
        b.bar(*LONG_SIGNAL)
        b.bar(20000.5, 20007.0, 20000.0, 20006.0)
        self.assertEqual(simulate(b.bars, Params()).trades, [])

    def test_session_follows_dst(self):
        b = Builder(datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc))   # 08:00 EDT, after the US clock change
        b.flat(120)                                                  # signal at 14:00Z = 10:00 EDT
        b.bar(*LONG_SIGNAL)
        b.bar(20000.5, 20007.0, 20000.0, 20006.0)
        self.assertEqual(len(simulate(b.bars, Params()).trades), 1)

    def test_non_contiguous_next_bar_discards_signal(self):
        b = Builder()
        b.flat(120)
        b.bar(*LONG_SIGNAL)
        b.skip(5)
        b.bar(20000.5, 20007.0, 20000.0, 20006.0)
        r = simulate(b.bars, Params())
        self.assertEqual(r.trades, [])
        self.assertEqual(r.skipped["gap"], 1)

    def test_flatten_at_1659_et(self):
        b = Builder()
        b.flat(120)
        b.bar(*LONG_SIGNAL)                                          # 10:00 ET
        for _ in range(419):                                         # 15:01Z .. 21:59Z, never touches stop/target
            b.bar(20000.5, 20001.0, 20000.0, 20000.5)
        t = only_trade(self, simulate(b.bars, Params()))
        self.assertEqual(t.reason, "FLATTEN")
        self.assertEqual(t.exit_time, datetime(2026, 3, 2, 21, 59, tzinfo=timezone.utc))   # 16:59 ET
        self.assertAlmostEqual(t.exit_price, 20000.25)
        self.assertAlmostEqual(t.pnl_net, -0.5 * 12 - 16.8)

    def test_sizing(self):
        t = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0), params=Params(max_contracts=100)))
        self.assertEqual(t.qty, 16)                                  # floor(100 / 6)
        r = scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0), params=Params(risk_per_trade=5))
        self.assertEqual((r.trades, r.skipped["size"]), ([], 1))

    def test_minimum_stop_is_8_ticks(self):
        b = Builder()
        b.flat(120, half=0.25)                                       # ATR 0.5 -> 1.5*ATR = 0.75 < 2.0
        b.bar(19999.75, 20000.5, 19999.0, 20000.25)
        b.bar(20000.25, 20010.0, 20000.0, 20009.0)
        t = only_trade(self, simulate(b.bars, Params()))
        self.assertEqual(t.stop_ticks, 8)

    def test_trend_filter(self):
        b = Builder()
        b.flat(120)
        b.flat(25, price=19980.0)
        b.bar(19979.5, 19981.0, 19978.0, 19980.5)                    # close below a lagging EMA50
        b.bar(19980.5, 19981.0, 19980.0, 19980.5)
        self.assertEqual(simulate(b.bars, Params(use_trend_filter=True)).trades, [])
        self.assertEqual(len(simulate(b.bars, Params(use_trend_filter=False)).trades), 1)

    def test_cost_formula_matches_net_r(self):
        scenarios = [
            scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0)),
            scenario(LONG_SIGNAL, (20000.5, 20001.0, 19997.0, 19998.0)),
            scenario(LONG_SIGNAL, (20000.5, 20001.0, 20000.0, 20000.5), (19990.0, 19991.0, 19989.0, 19990.0)),
            scenario(SHORT_SIGNAL, (19999.5, 19999.75, 19993.0, 19994.0)),
        ]
        for r in scenarios:
            for t in r.trades:
                self.assertAlmostEqual(t.r_net, t.r_gross - t.cost_r, places=9)
        target = scenarios[0].trades[0]
        self.assertAlmostEqual(target.cost_r, (2.8 + 1 * 0.25 * 2) / (3.0 * 2))   # one slipped leg
        stop = scenarios[1].trades[0]
        self.assertAlmostEqual(stop.cost_r, (2.8 + 2 * 0.25 * 2) / (3.0 * 2))     # entry and exit slipped

    def test_zero_costs_give_exact_2r_and_minus_1r(self):
        free = Params(commission_per_contract=0.0, slippage_ticks=0.0)
        win = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0), params=free))
        loss = only_trade(self, scenario(LONG_SIGNAL, (20000.5, 20001.0, 19997.0, 19998.0), params=free))
        self.assertAlmostEqual(win.r_net, 2.0)
        self.assertAlmostEqual(loss.r_net, -1.0)


class IndicatorTests(unittest.TestCase):
    def test_atr_wilder_known_values(self):
        t = T0
        bars = [Bar(t, 100, 101, 99, 100), Bar(t + timedelta(minutes=1), 100, 103, 99, 100)]
        atr = wilder_atr(bars)
        self.assertAlmostEqual(atr[0], 2.0)
        self.assertAlmostEqual(atr[1], 3.0)                          # (2*1 + 4) / 2
        b = Builder()
        b.flat(20)
        b.bar(100.0, 108.0, 92.0, 100.0)
        b.bars = [Bar(x.start, 100, 101, 99, 100) for x in b.bars[:-1]] + [b.bars[-1]]
        atr = wilder_atr(b.bars)
        self.assertAlmostEqual(atr[19], 2.0)
        self.assertAlmostEqual(atr[20], (2.0 * 13 + 16.0) / 14)      # 3.0


class LoaderAndStatsTests(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_load_sorts_dedupes_and_parses_z(self):
        path = self.write("timestamp,open,high,low,close,volume\n"
                          "2026-03-02T15:01:00Z,2,3,1,2,10\n"
                          "2026-03-02T15:00:00Z,1,2,0.5,1.5,5\n"
                          "2026-03-02T15:00:00Z,1,2,0.5,1.75,6\n")
        with contextlib.redirect_stderr(io.StringIO()):
            bars = load_bars(path)
        self.assertEqual([b.c for b in bars], [1.75, 2.0])
        self.assertEqual(bars[0].start, datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))

    def test_load_naive_timestamps_use_input_tz(self):
        path = self.write("timestamp,open,high,low,close,volume\n2026-03-02 10:00:00,1,2,0.5,1.5,5\n")
        self.assertEqual(load_bars(path, "America/New_York")[0].start, datetime(2026, 3, 2, 15, 0, tzinfo=timezone.utc))

    def test_load_rejects_bad_data(self):
        for text in ("timestamp,open,high,low,close\n2026-03-02T15:00:00Z,1,0.5,2,1\n",
                     "timestamp,open,high,low,close\nnot-a-date,1,2,0.5,1\n",
                     "timestamp,open,high,low\n2026-03-02T15:00:00Z,1,2,0.5\n",
                     "timestamp,open,high,low,close\n"):
            with self.assertRaises(ValueError):
                load_bars(self.write(text))

    def test_summary_small_sample_flag_and_determinism(self):
        r = scenario(LONG_SIGNAL, (20000.5, 20007.0, 20000.0, 20006.0))
        s = summarize(r.trades)
        self.assertTrue(s["small_sample"])
        self.assertEqual(s["n"], 1)
        self.assertIsNone(s["ci_r"])                                 # one day cannot be resampled
        many = r.trades * 3
        for i, t in enumerate(many):
            many[i] = bt.replace(t, day=f"2026-03-{2 + i:02d}")
        self.assertEqual(summarize(many)["ci_r"], summarize(many)["ci_r"])


class CliSmokeTests(unittest.TestCase):
    """Synthetic data only proves the tester runs end to end and is deterministic."""

    def test_cli_on_synthetic_data(self):
        with tempfile.TemporaryDirectory() as d:
            csv_path, trades_path = os.path.join(d, "synth.csv"), os.path.join(d, "trades.csv")
            subprocess.run([sys.executable, os.path.join(HERE, "synth_data.py"), "--days", "21", "--out", csv_path],
                           check=True, capture_output=True)
            outputs = []
            for _ in range(2):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(bt.main([csv_path, "--trades-out", trades_path, "--boot-reps", "200", "--compare"]), 0)
                outputs.append(buf.getvalue())
            self.assertEqual(outputs[0], outputs[1])
            self.assertIn("SIN ordenes reales", outputs[0])
            self.assertIn("COMPARACION DE VARIANTES", outputs[0])
            self.assertTrue(os.path.exists(trades_path))
            result = simulate(load_bars(csv_path), Params())
            for t in result.trades:
                self.assertAlmostEqual(t.r_net, t.r_gross - t.cost_r, places=9)
            if len(result.trades) < bt.MIN_TRADES_WARN:
                self.assertIn("MUESTRA INSUFICIENTE", outputs[0])


if __name__ == "__main__":
    unittest.main()
