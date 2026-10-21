# EvalBot V0.4 — experimental adaptive regime evaluation

The client evaluation bundle is distributed as `EvalBot_V04_Cliente_Evaluacion.zip` in the conversation. It contains the original tester, adaptive filters, tests, XGBoost baseline and README.

## Scope

- The original Python backtest remains the default and is intended as an *unverified* approximation of NinjaTrader V0.3.
- Opt-in `adaptive_guard=true` identifies range expansion relative to prior ATR, abnormal volume, fast trend and elevated volatility.
- It suspends *new entries* after shocks, reduces size under high volatility and supports timestamped scheduled events via `--events`.
- Unexpected social-media posts cannot be anticipated: no Truth Social integration or verified event feed exists.
- `train_xgboost.py` provides a chronological 60/20/20 research baseline with embargo and out-of-sample AUC/accuracy. This is not a production trading model.

## Local checks

Earlier local tests were reported, but their source files are not all present in this repository; results are **not reproducible from a clean clone**.
Adaptive tests cannot be independently rerun from this repository yet.
No real MNQ dataset, broker connection, Strategy Analyzer parity test or profitability validation was performed.

## Important

**The live NinjaTrader strategy is still V0.3.** The V0.4 adaptive guard is research-only. Do not interpret the Python tester as a verified broker execution engine. Before release, reconcile fills, stop/target semantics, exchange sessions, time zones, gaps and slippage with Strategy Analyzer and independent tick data.
