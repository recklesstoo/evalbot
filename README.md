# EvalBot AI — MVP 0.1

**Experimental, signal-only prototype.** No order submission, broker login, or trained neural network.

## Architecture

Rithmic → NinjaTrader 8 → NinjaScript Data Bridge → local HTTP receiver → regime/signal engine → browser dashboard.

The intended implementation uses a lightweight NinjaTrader indicator to export closed 1-minute OHLCV bars, a local analysis engine to classify trend/range and identify liquidity sweeps, and a read-only dashboard. NinjaTrader remains the licensed data-feed client. The operator confirms orders manually.

## Development milestones

1. Compile and validate NinjaScript bridge in NinjaTrader 8.
2. Compare exported bars, timestamps, and session boundaries with NinjaTrader.
3. Add 5-session regime detection, session VWAP and liquidity levels.
4. Port EvalBot V1.2 signals and reconcile its 205 historical trades.
5. Train ML models with walk-forward evaluation, calibrated probabilities and fees/slippage.
6. Add account-level risk simulation and monitoring.

## Risk and compliance

Do not distribute licensed market data or broker credentials. Respect Apex, NinjaTrader and Rithmic terms. No automated order submission in accounts without explicit authorization. The prototype has not been validated for live trading.

## License

All rights reserved unless a license is added by the owner. No third-party NinjaTrader code is copied. The morluto/rea project is research tooling only, not a runtime dependency.
