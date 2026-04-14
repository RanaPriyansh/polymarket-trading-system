# Time-Series Backtest Results — 2026-04-15

## Data Quality

- **Time-series data**: 14,948 trades across 30 markets, collected via Polymarket Data API
- **OHLCV candles**: 1h (3,989), 4h (2,360), 1d (752) across 22-28 markets
- **Date range**: 2026-01-07 to 2026-04-15
- **Data source**: Real trade history from data-api.polymarket.com (not single-snapshot)

## 1h Candle Results (3,989 snapshots, 28 markets)

| Strategy | Trades | Win Rate | PnL | Return | Sharpe |
|---|---|---|---|---|---|
| statistical | 423 | 90.3% | $59,621 | 5962.1% | 0.32 |
| momentum | 876 | 74.2% | $76,104 | 7610.4% | 0.25 |
| mean_reversion | 1,754 | 18.3% | $45,927 | 4592.7% | 0.30 |
| volume_breakout | 84 | 7.1% | $591 | 59.1% | 0.26 |

### Monitoring Data Comparison (single-snapshot, 188 markets)

| Strategy | Trades | Win Rate | PnL | Return |
|---|---|---|---|---|
| monitoring_momentum | 78 | 79.5% | $4,382 | 438.2% |
| monitoring_statistical | 27 | 74.1% | $1,369 | 136.9% |

## 4h Candle Results (2,360 snapshots, 28 markets)

| Strategy | Trades | Win Rate | PnL | Return | Sharpe |
|---|---|---|---|---|---|
| statistical | 242 | 87.2% | $33,002 | 3300.2% | 0.37 |
| momentum | 530 | 70.8% | $45,007 | 4500.7% | 0.26 |
| mean_reversion | 1,012 | 16.7% | $24,074 | 2407.4% | 0.28 |
| volume_breakout | 85 | 4.7% | $355 | 35.5% | 0.18 |

## Daily Candle Results (752 snapshots, 22 markets)

| Strategy | Trades | Win Rate | PnL | Return | Sharpe |
|---|---|---|---|---|---|
| statistical | 89 | 91.0% | $12,373 | 1237.3% | 0.38 |
| momentum | 182 | 68.1% | $12,494 | 1249.4% | 0.25 |
| mean_reversion | 266 | 16.5% | $5,890 | 589.0% | 0.27 |
| volume_breakout | 70 | 8.6% | $574 | 57.4% | 0.26 |

## Key Findings

1. **Time-series data dramatically increases backtest coverage**: From 188 single-snapshot rows to 3,989 time-series snapshots across 28 markets spanning 3+ months.
2. **Statistical strategy remains strongest**: 90.3% win rate on 1h candles, 91% on daily candles.
3. **Momentum strategy trades more frequently with time-series**: 876 trades vs 78 with monitoring data — 11x more signals captured.
4. **Volume breakout still underperforms**: Consistently low win rate (4.7-8.6%) across all timeframes, confirming parameters need tuning.
5. **Mean reversion low win rate but positive PnL**: At 18.3% win rate on 1h data, but still profitible due to large wins vs small losses — classic fat-tail profile.
6. **Important caveat**: Returns >1000% are still unrealistic — position sizing uses 2% of initial capital per trade with compounding across many markets simultaneously. Real implementation would have capital constraints.

## Data Pipeline

- **New module**: `data_collectors/timeseries_collector.py` — Collects trade data from Polymarket Data API, aggregates into OHLCV candles, stores in `data/timeseries.db`
- **New module**: `analysis/timeseries_backtest.py` — Runs backtests using time-series data with comparison to monitoring-only approach
- **New database**: `data/timeseries.db` — Contains raw_trades, price_candles, market_snapshots tables