# Automatic execution — EvalBot AutoTrader V0.2

This is an **experimental native NinjaTrader 8 Strategy** that can submit entries and attached protective exits using NinjaTrader's managed order API. It does not depend on the Python signal engine, which remains a separate research prototype.

## Installation and evaluation
1. Copy `ninjatrader/EvalBotAutoTrader.cs` into NinjaTrader 8's NinjaScript Strategies directory, or paste into a new Strategy named `EvalBotAutoTrader`.
2. Compile in NinjaScript Editor. **Compilation on an actual NinjaTrader installation has not yet been verified.**
3. Run in Strategy Analyzer on a 1-minute MNQ chart, then Sim101. Include realistic commissions and slippage.
4. Confirm order names, quantity, attached stop/target, daily reset, fills, partial fills, cancellation/rejection handling, and session boundaries.
5. For live accounts, leave `AllowLiveAccount=false` unless the account provider expressly authorizes automation and the implementation has passed a complete risk review.

## Current behavior
- Native sweep/reclaim entries, ATR stop and reward/risk profit target.
- Per-trade sizing from point value, daily P&L threshold, trade count cap.
- Calendar-date daily reset in chart time, optional session hours.
- Fail-closed rejection behavior; simulated-account default.
- No external broker credentials, network dependencies, neural model or guaranteed profitability.

## Known limitations / release blockers
- The daily P&L counter is strategy-scoped, **not account-wide**. Other strategies and manual trades are not included.
- Threshold checks run on bar close and cannot guarantee a hard loss cap during gaps or slippage.
- Working protective order confirmation, partial fills, reconnection reconciliation, pending order timeout, and emergency flat need more testing.
- Sim101 name check is simplistic; verify actual simulation account names.
- Historical/backtest execution semantics differ from live.
- 5-day regime adaptation, VWAP, neural inference, and model-based risk filtering are not implemented yet.
- `OnExecutionUpdate` and `OnOrderUpdate` behaviors must be tested against actual NinjaTrader 8.
- Some brokers and evaluation programs prohibit automation, even if the customer acknowledges a sales disclaimer. Do not use to evade these restrictions.

## Commercial considerations
Present execution capability accurately, disclose risk, obtain broker/data-provider permission where needed, and do not promise evaluation success. Product licensing, data rights, compliance and technical support remain to be designed.
