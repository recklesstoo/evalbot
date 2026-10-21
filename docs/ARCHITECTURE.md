# Architecture

## Modules

- **NT8 Data Bridge:** NinjaScript indicator on 1-minute bars, signal-only and nonblocking.
- **Receiver:** local authenticated ingestion, validates OHLCV and UTC timestamps, deduplicates and records gaps.
- **Market Regime:** trend/range/volatility classifier using only past bars; future 5-session rolling window.
- **Liquidity Engine:** sweep/reclaim and reference levels.
- **Signal Engine:** LONG/SHORT/WAIT with entry, stop and take-profit; no order routing.
- **Dashboard:** browser-based local status, signals and data freshness.
- **Model Training (future):** offline XGBoost/MLP/LSTM; strict walk-forward and ONNX inference when justified.

## Security

Bind local services to loopback, require an ingestion token, never commit secrets. A Linux/Windows VM split needs authenticated transport and explicit firewall policy. Never expose ingestion publicly.

## Validation

Check timestamps (Panama vs New York daylight saving), VWAP resets, closed-bar semantics, missing bars, memory bounds, commissions, slippage, and identical signal reconstruction.
