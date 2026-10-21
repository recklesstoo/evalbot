# Client review response — 2026-10-21

**Status: REJECTED / NOT READY FOR CLIENT APPROVAL.**

The full local evaluation package is not yet fully present in GitHub. CI configuration alone does not establish reproducibility. A clean clone currently lacks tester/backtest.py and other Python modules, so the Python tests cannot pass.

## Safety

NinjaTrader's native strategy has an unconditional `AccountWideRiskGuardImplemented() { return false; }` entry gate until account-level risk accounting and reconciliation are implemented and validated. It is intentionally unable to open new orders. The strategy is not compiled or tested in NinjaTrader.

## Required acceptance gates

1. All referenced scripts and tests versioned and passing in clean-clone CI.
2. Per-candidate stop-dependent commission/slippage; horizon mark-to-market; contiguous historical feature windows; mutual exclusion between long and short; data provenance.
3. Daily block bootstrap, permutation baseline, monthly purged and embargoed walk-forward; evaluate on real sweep signals, not arbitrary bars.
4. Compile NinjaTrader script; validate trading-hours resets, account-wide risk, restarts, partial fills, broker disconnects, working orders and stops.
5. Test with independently sourced real MNQ/MES/MGC market data; show net expectancy and drawdown, with confidence intervals.

**Do not interpret synthetic tests as evidence of profitability.**
