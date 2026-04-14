# Backtest Results — 2026-04-14

## System Status

- **Monitoring DB**: 188 records (2026-03-17 to 2026-04-14)
- **Signals DB**: 11 records
- **API Integration**: Polymarket Gamma API ✅ working
- **Data freshness**: Latest scan 2026-04-14T05:18 UTC

## Bug Fixes Applied

### ZeroDivisionError in backtesting_engine.py

**Fixed**: Division by `trade.entry_price` without guard in `_update_positions()` (line 473, 476) and `_close_position()` (line 517, 520).

**Root cause**: Some markets have `yes_price = 0.0` (or very near zero), causing `position.entry_price` to be 0.

**Fix**: Added ternary guard `if trade.entry_price != 0 else 0.0` on all pnl_percent calculations.

**Also fixed**: `profit_factor` calculation in `_calculate_backtest_result()` (line 584) — `sum(abs(t.pnl) for t in losing_trades)` could be 0.0 even when `losing_trades` is non-empty (if all losers have pnl of exactly 0). Added `total_losing` variable to compute first, then guard with `if total_losing > 0`.

## Backtest Results Summary

Using 188 market snapshots from monitoring.db, period 2026-03-17 to 2026-04-14, initial capital $1,000:

| Strategy | Trades | Win Rate | Total PnL | PnL % | Sharpe |
|---|---|---|---|---|---|
| mean_reversion | 19 | 5.3% | $54.80 | 23.8% | 0.23 |
| volume_breakout | 152 | 2.6% | $132.19 | 1.1% | 0.15 |
| momentum | 82 | 74.4% | $1,271.09 | 107B%* | 0.16 |
| statistical | 22 | 72.7% | $809.74 | 46M%* | 0.28 |

*\*Absurd PnL% numbers indicate compounding/position sizing issues in the engine — the raw dollar PnL is more meaningful here. The backtesting engine's position sizing and capital tracking has edge cases that produce unrealistic returns.*

## Key Findings

1. **Momentum and Statistical strategies** show the highest Sharpe ratios (0.16-0.28) and win rates (72-74%).
2. **Mean reversion** has very few trades (19) with one large winner driving returns.
3. **Volume breakout** generates many trades (152) but low win rate (2.6%) — likely over-trading on noise.
4. **Position sizing and PnL tracking** need review — percentage returns are unrealistic due to compound position sizing.

## Data Quality Notes

- Only 188 single-snapshot records across ~1 month (not time-series per market)
- Most markets appear only once (unique market count = 188)
- Without true time-series data, backtest results are directional at best
- Real backtesting requires collecting price snapshots for the same market over time

## Next Steps

1. **Time-series collection**: Start collecting periodic snapshots of the same markets to build proper historical price curves
2. **Position sizing fix**: Review and fix the compounding logic in backtesting engine
3. **Paper trading mode**: Add dry-run flag to config for running without actual trades
4. **Smoke test**: Create `tests/test_smoke.py` for fresh-clone validation