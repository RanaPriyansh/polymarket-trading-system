# Polymarket Trading System

## What We Built

A comprehensive trading system for Polymarket that replaces the old paper trading alerts (which only monitored 3 markets) with a system that monitors 100+ markets.

## Components

### 1. Data Collection (`data_collectors/`)
- `market_data_collector.py` - Collects market data, prices, volumes, order books
- Stores data in SQLite database for historical analysis

### 2. Analysis (`analysis/`)
- `comprehensive_monitor.py` - Monitors 100+ markets for opportunities
- `signal_generator.py` - Generates trading signals using multiple strategies:
  - Mean reversion
  - Volume-based signals
  - Spread arbitrage
  - Order book analysis
  - Liquidity signals

### 3. Monitoring (`monitoring/`)
- Real-time market monitoring
- Automated scanning every 60 minutes
- Signal generation every 30 minutes
- Results saved to database and files

## What's Running Now

### Cron Jobs:
1. **comprehensive-polymarket-monitor** - Runs every 60 minutes
   - Analyzes 100+ markets
   - Finds trading opportunities
   - Sends top 5 to Telegram

2. **polymarket-signal-generator** - Runs every 30 minutes
   - Analyzes 10 specific markets
   - Generates trading signals
   - Sends high-confidence signals to Telegram

### What We Stopped:
- **88 paper trading alert cron jobs** that were spamming Telegram
- All monitoring only 3 markets (Eric Trump 2028, Fed 25bps, Fed No Change)

## Key Improvements

1. **Scale**: From 3 markets → 100+ markets
2. **Intelligence**: Multiple trading strategies, not just price alerts
3. **Efficiency**: Consolidated from 88 redundant cron jobs to 2 intelligent ones
4. **Data Storage**: All results saved to database for historical analysis
5. **Signal Quality**: Confidence scores, risk levels, potential returns

## Trading Strategies Implemented

1. **Low Volume + Extreme Pricing**
   - Find markets with <$50K volume and extreme prices (>85% or <15%)
   - Expect mean reversion as more traders enter

2. **High Volume Opportunities**
   - Markets with >$500K volume indicate strong interest
   - Look for mispricing in popular markets

3. **Spread Arbitrage**
   - Capture wide spreads between Yes/No prices
   - Particularly in illiquid markets

4. **Order Book Imbalance**
   - Analyze bid/ask size ratios
   - Trade in direction of order book pressure

5. **Volume Spike Detection**
   - Identify sudden increases in trading activity
   - May indicate insider information or news

## Data Storage

- **SQLite databases** for market data, signals, and monitoring results
- **JSON files** for each scan with timestamps
- **Historical analysis** capability for backtesting

## Next Steps

1. **Add more markets** to signal generator (expand beyond 10)
2. **Implement backtesting** to validate strategies
3. **Add risk management** with position sizing
4. **Integrate with Polymarket API** for actual trading
5. **Add machine learning models** for better predictions

## Files Structure

```
polymarket-trading-system/
├── architecture.md
├── config/
│   └── settings.py
├── data_collectors/
│   └── market_data_collector.py
├── analysis/
│   └── signal_generator.py
├── monitoring/
│   └── comprehensive_monitor.py
├── data/
│   ├── market_data.db
│   ├── signals.db
│   └── monitoring.db
└── README.md
```

## Quick Start (Verified 2026-04-14)

```bash
cd /root/projects/polymarket-trading-system

# Smoke test — verifies imports, databases, backtesting, and API connectivity
python3 tests/test_smoke.py

# Run comprehensive monitor (fetches 100+ markets from Polymarket Gamma API)
python3 monitoring/comprehensive_monitor.py

# Run signal generator
python3 analysis/signal_generator.py

# Run backtesting engine on historical data
python3 -c "
import asyncio, sqlite3, json
from datetime import datetime
from analysis.backtesting_engine import BacktestingEngine, StrategyType
conn = sqlite3.connect('data/monitoring.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM monitoring_results').fetchall()
conn.close()
data = [dict(r) for r in rows]
for d in data:
    if isinstance(d.get('opportunities'), str):
        try: d['opportunities'] = json.loads(d['opportunities'])
        except: d['opportunities'] = []
engine = BacktestingEngine(initial_capital=1000.0)
result = asyncio.run(engine.run_backtest(data, StrategyType.MEAN_REVERSION, datetime(2026,3,17), datetime(2026,4,14)))
print(f'{result.strategy_name}: {result.total_trades} trades, {result.win_rate:.1%} win, PnL \${result.total_pnl:.2f}')
"
```

**Dependencies**: `aiohttp`, `numpy`, `pandas` (pip install if missing)

## Bug Fixes (2026-04-14)

- **ZeroDivisionError** in `backtesting_engine.py`: Fixed division by `trade.entry_price` (can be 0 for extreme-priced markets) and division by `sum(abs(t.pnl))` (can be 0.0 when losing trades have zero nominal PnL). See `WORKLOG.md` for details.

## Current Status

✅ System architecture designed
✅ Data collection pipeline built
✅ Analysis engine with multiple strategies
✅ Monitoring and alerting system
✅ Automated workflows running
✅ Smoke test created and passing
✅ Backtesting engine bug-fixed and verified on all 4 strategies
⚠️ Trading execution not yet implemented (next step)
⚠️ Position sizing produces unrealistic % returns — needs review

## Telegram Alerts

Instead of spamming you with 3 market alerts every 5 minutes, you'll now receive:
- Top 5 opportunities from 100+ markets every 60 minutes
- High-confidence trading signals every 30 minutes
- Much more valuable and less spammy!