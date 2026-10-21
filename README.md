# EvalBot — experimental NinjaTrader strategy and Python research

**Status: NOT APPROVED for production or profitability claims.**

## Two separate components

- `ninjatrader/EvalBotAutoTrader.cs`: Native NinjaTrader 8 Strategy that can submit real orders to the selected account. Automatic execution is **disabled by default** and must be explicitly enabled. Its safety and order handling have **not** been compiled or validated in NinjaTrader.
- `engine/` and `ninjatrader/EvalBotDataBridge.cs`: separate signal-only research prototype; not required by the native Strategy.
- `tester/`: Python experimental research. The repo is currently **incomplete**; required tester dependencies and scripts must be added before reproducible tests can be claimed.

## Known release blockers

1. Full reproducibility from a clean clone, pinned dependencies and CI.
2. NinjaTrader compilation, strategy-analyzer parity, account-wide risk controls, restart and order reconciliation.
3. Reliable out-of-sample evaluation on real market data.

See `docs/V05_GENERIC_RESEARCH.md` and `docs/V04_ADAPTIVE_EVALUATION.md`. Synthetic tests do not establish profitability.

## License

All rights reserved unless a license is explicitly added by the repository owner.
