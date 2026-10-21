# Execution, data and operational constraints

The repository includes a **native NinjaTrader 8 strategy that submits orders** when the operator explicitly enables automatic execution. This is distinct from the Python signal-only research prototype.

The strategy is **experimental and unverified on NinjaTrader**. The software's strategy-level realized P&L and daily trade limits are **not account-wide** and do not include other strategies or manual orders. Stop, target, gap, reconnection, working-order and partial-fill behavior require platform validation. An operator enabling the strategy does not replace broker or evaluation-program permissions.

Data-provider agreements govern market-data export, retention and redistribution. Do not distribute broker credentials, proprietary binaries or licensed feed data. Do not promise evaluation success or profitability. Review current provider terms before live use.
