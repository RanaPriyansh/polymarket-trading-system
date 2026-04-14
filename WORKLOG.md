# WORKLOG — polymarket-trading-system

## 2026-04-14 — Builder Engine Run

### Completed
- **Fixed ZeroDivisionError bugs** in `analysis/backtesting_engine.py`:
  - `_update_positions()`: Guard on `trade.entry_price` in pnl_percent calculation (lines 473, 476)
  - `_close_position()`: Same guard (lines 517, 520)
  - `_calculate_backtest_result()`: Fix `profit_factor` when losing trades have zero total PnL (line 584)
- **Ran backtest suite** on all 4 strategies using 188 market snapshots from monitoring.db
- **Saved backtest results** to `outputs/backtest-results-2026-04-14.md`

### Findings
- All 4 strategy backtests now run without error
- Momentum (74.4% win rate) and Statistical (72.7%) strategies outperform on win rate
- Volume breakout strategy over-trades (152 trades, 2.6% win rate)
- Position sizing produces unrealistic % returns — needs review
- Data is single-snapshot (not time-series), limiting backtest reliability

## 2026-04-14 — Builder Engine Run (17:15)

### Completed
- **Fixed position sizing compounding bug** — 4 root causes in `backtesting_engine.py`:
  - Compounding position sizing (capital * 0.02 → initial_capital * 0.02)
  - Double-counting PnL on close (added proceeds AND profit)
  - No short direction handling in capital accounting
  - Misleading total_pnl_percent (averaged per-trade % → portfolio-level return)
- **Re-ran backtests** — realistic results: momentum 226% (was 107B%), statistical 104% (was 46M%)
- **Committed and pushed** — `9320349`
- All smoke tests passing

### Backtest Results (v2 — fixed)

| Strategy | Trades | Win Rate | PnL | Return | Final Capital |
|---|---|---|---|---|---|
| momentum | 45 | 75.6% | $2,261 | 226.1% | $3,261 |
| statistical | 22 | 72.7% | $1,041 | 104.1% | $2,041 |
| volume_breakout | 152 | 2.6% | $142 | 14.2% | $1,142 |
| mean_reversion | 19 | 5.3% | $55 | 5.5% | $1,055 |

### What Still Needs Work
1. ❌ Time-series data collection (single-snapshot limits backtest validity)
2. ❌ Paper trading / dry-run mode
3. ❌ Volume breakout tuning (152 trades / 2.6% win = bad params)
4. ❌ Trading execution module
5. ❌ ML models implementation

### System Status
- Monitoring script: ✅ fetches 100+ markets from Gamma API
- Signal generator: ✅ generates signals
- Backtesting engine: ✅ runs all strategies after bug fix
- Database: 188 records in monitoring.db, 11 in signals.db