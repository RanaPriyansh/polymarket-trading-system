# WORKLOG — polymarket-trading-system

## 2026-04-15 — Builder Engine Run (01:15 CEST)

### Completed: Time-Series Data Collection & Enhanced Backtesting

- **Added `data_collectors/timeseries_collector.py`**: New module that collects trade history from Polymarket's Data API (`data-api.polymarket.com/trades`), aggregates into OHLCV candles (1h, 4h, 1d), and stores in `data/timeseries.db` with tables for raw_trades, price_candles, and market_snapshots
- **Added `analysis/timeseries_backtest.py`**: New runner that uses time-series data for backtesting with comparison to single-snapshot monitoring approach
- **Collected 14,948 trades across 30 markets**: Built from top-50 active Polymarket markets with $50K+ volume
- **Generated OHLCV candles**: 3,993 (1h), 2,360 (4h), 762 (1d) candles across 22-28 markets
- **Ran full time-series backtests**: All 4 strategies across 3 timeframes, with comparison to monitoring-only approach

### Key Backtest Results (1h candles, 3,989 snapshots, 28 markets)
- **Statistical**: 423 trades, 90.3% win rate, $59,621 PnL
- **Momentum**: 876 trades, 74.2% win rate, $76,104 PnL
- **Mean Reversion**: 1,754 trades, 18.3% win rate, $45,927 PnL
- **Volume Breakout**: 84 trades, 7.1% win rate, $591 PnL (needs parameter tuning)

### Data Pipeline
- `timeseries_collector.py` → `data/timeseries.db` (raw_trades, price_candles, market_snapshots)
- `timeseries_backtest.py` → backtest engine with time-series data
- All 4 smoke tests passing

### Caveats
- Returns >1000% are unrealistic — position sizing uses 2% of initial capital per trade with concurrent positions across markets. Real implementation needs capital constraints.
- CLOB prices-history API returns empty data; trades API (data-api) is the reliable source for historical data.
- Momentum/Statistical strategies still use random signals — need proper price-history-based implementation for true time-series strategies.