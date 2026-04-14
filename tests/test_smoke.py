#!/usr/bin/env python3
"""
Smoke test for polymarket-trading-system.
Verifies the project can be cloned, imported, and core paths work.
Run from repo root: python3 tests/test_smoke.py
"""

import sys
import os
import asyncio
import sqlite3

# Ensure repo root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """All core modules import without error."""
    from config.settings import POLYMARKET_API, TRADING_CONFIG
    from monitoring.comprehensive_monitor import ComprehensiveMarketMonitor
    from analysis.signal_generator import SignalGenerator
    from analysis.backtesting_engine import BacktestingEngine, StrategyType
    print("✅ All core modules import OK")

def test_databases():
    """SQLite databases are accessible and have expected tables."""
    for db_path in ['data/monitoring.db', 'data/signals.db']:
        assert os.path.exists(db_path), f"Missing database: {db_path}"
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert len(tables) >= 1, f"No tables in {db_path}"
        conn.close()
    print("✅ Databases accessible")

def test_backtesting_engine():
    """Backtesting engine can be instantiated and run with synthetic data."""
    from analysis.backtesting_engine import BacktestingEngine, StrategyType, BacktestTrade
    from datetime import datetime

    engine = BacktestingEngine(initial_capital=1000.0)
    assert engine.initial_capital == 1000.0

    # Verify no ZeroDivisionError with zero-price markets
    synthetic_data = [{
        "timestamp": datetime.now().isoformat(),
        "market_slug": "test-market",
        "market_question": "Test market?",
        "volume": 50000,
        "yes_price": 0.0,  # Edge case: zero price
        "no_price": 1.0,
        "spread": 1.0,
        "risk_level": "medium",
        "potential_return": 0.5,
        "opportunities": [],
    }]
    result = asyncio.run(engine.run_backtest(
        market_data=synthetic_data,
        strategy_type=StrategyType.MEAN_REVERSION,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
    ))
    assert result is not None
    print("✅ Backtesting engine runs without ZeroDivisionError")

def test_api_connectivity():
    """Polymarket Gamma API is reachable."""
    from monitoring.comprehensive_monitor import ComprehensiveMarketMonitor

    async def check():
        monitor = ComprehensiveMarketMonitor()
        await monitor.start_session()
        markets = await monitor.get_all_markets(limit=1)
        await monitor.close_session()
        return len(markets) > 0

    result = asyncio.run(check())
    assert result, "Polymarket API returned no markets"
    print("✅ Polymarket Gamma API reachable")

def main():
    print("=== polymarket-trading-system smoke test ===\n")
    test_imports()
    test_databases()
    test_backtesting_engine()
    test_api_connectivity()
    print("\n=== All checks passed ✅ ===")

if __name__ == "__main__":
    main()