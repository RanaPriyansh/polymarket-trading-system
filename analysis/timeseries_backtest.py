#!/usr/bin/env python3
"""
Time-Series Backtest Runner for Polymarket Trading System

Runs backtests using real trade-derived OHLCV data from the timeseries database,
replacing the single-snapshot approach with proper time-series analysis.

Strategy improvements:
- Momentum: Uses actual price changes (close - open, moving averages)
- Mean Reversion: Uses z-scores computed from rolling price history
- Volume Breakout: Uses volume percentiles computed from actual trade volumes
- Statistical: Uses price deviation from VWAP rather than random z-scores
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
import statistics

from analysis.backtesting_engine import (
    BacktestingEngine, StrategyType, BacktestResult, BacktestTrade
)

DB_PATH = "/root/projects/polymarket-trading-system/data/timeseries.db"
MONITORING_DB = "/root/projects/polymarket-trading-system/data/monitoring.db"
OUTPUT_DIR = "/root/projects/polymarket-trading-system/outputs"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TimeseriesBacktestRunner:
    """Runs backtests using time-series OHLCV data from the trades database."""

    def __init__(self, db_path: str = DB_PATH, initial_capital: float = 1000.0):
        self.db_path = db_path
        self.initial_capital = initial_capital

    def load_candle_data(self, timeframe: str = "1h",
                          min_candles: int = 5,
                          limit_markets: int = None) -> List[Dict]:
        """Load OHLCV candle data for backtesting.

        Args:
            timeframe: Candle timeframe ("1h", "4h", "1d")
            min_candles: Minimum number of candles per market
            limit_markets: Max number of markets to include

        Returns:
            List of candle dicts sorted by timestamp
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # First, find markets with enough candles
        cursor.execute('''
            SELECT condition_id, COUNT(*) as candle_count
            FROM price_candles
            WHERE timeframe = ?
            GROUP BY condition_id
            HAVING candle_count >= ?
            ORDER BY candle_count DESC
        ''', (timeframe, min_candles))

        qualified_markets = cursor.fetchall()
        if limit_markets:
            qualified_markets = qualified_markets[:limit_markets]

        if not qualified_markets:
            logger.warning(f"No markets with {min_candles}+ {timeframe} candles found")
            conn.close()
            return []

        # Get the question/slug for each market
        market_info = {}
        cursor.execute('''
            SELECT DISTINCT condition_id, slug, question
            FROM market_snapshots
        ''')
        for row in cursor.fetchall():
            market_info[row[0]] = {"slug": row[1], "question": row[2]}

        # Load candles for all qualified markets
        all_candles = []
        total_snapshots = 0

        for condition_id, candle_count in qualified_markets:
            info = market_info.get(condition_id, {"slug": condition_id[:20], "question": ""})

            cursor.execute('''
                SELECT timestamp, open_price, high_price, low_price, close_price,
                       volume, trade_count, condition_id, slug
                FROM price_candles
                WHERE condition_id = ? AND timeframe = ?
                ORDER BY timestamp ASC
            ''', (condition_id, timeframe))

            candles = cursor.fetchall()
            for c in candles:
                ts, open_p, high_p, low_p, close_p, vol, tc, cid, slug = c
                all_candles.append({
                    "id": cid,
                    "condition_id": cid,
                    "slug": slug or info["slug"],
                    "question": info["question"] or slug or cid[:30],
                    "yes_price": close_p,  # Current price = close of candle
                    "no_price": 1.0 - close_p,
                    "volume": vol or 0,
                    "liquidity": 0,
                    "timestamp": datetime.fromtimestamp(ts).isoformat(),
                    "open_price": open_p,
                    "high_price": high_p,
                    "low_price": low_p,
                    "close_price": close_p,
                    "trade_count": tc or 0,
                })

            total_snapshots += len(candles)

        conn.close()

        # Sort all candles by timestamp
        all_candles.sort(key=lambda x: x["timestamp"])

        logger.info(f"Loaded {len(all_candles)} {timeframe} candle snapshots from {len(qualified_markets)} markets")
        return all_candles

    def load_monitoring_data(self) -> List[Dict]:
        """Load monitoring snapshot data as fallback dataset."""
        conn = sqlite3.connect(MONITORING_DB)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, timestamp, market_slug, market_question, volume,
                   yes_price, no_price, spread, risk_level, potential_return
            FROM monitoring_results
            ORDER BY timestamp ASC
        ''')

        rows = cursor.fetchall()
        conn.close()

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "question": row[3] or row[2],
                "slug": row[2],
                "yes_price": row[5],
                "no_price": row[6],
                "volume": row[4],
                "liquidity": 0,
                "timestamp": row[1],
                "spread": row[7],
                "risk_level": row[8],
                "potential_return": row[9],
            })

        return data

    async def run_timeseries_backtest(self, timeframe: str = "1h",
                                 min_candles: int = 5,
                                 limit_markets: int = None) -> Dict:
        """Run backtests using real time-series data and compare with monitoring-data approach.

        Returns dict with results from timeseries-based and monitoring-based backtests.
        """
        # Load time-series data
        ts_data = self.load_candle_data(
            timeframe=timeframe,
            min_candles=min_candles,
            limit_markets=limit_markets
        )

        if not ts_data:
            logger.error("No time-series data available")
            return {"error": "No time-series data available"}

        # Build per-market time series for enhanced strategies
        market_series = defaultdict(list)
        for snap in ts_data:
            market_series[snap["id"]].append(snap)

        # Group data by timestamp for snapshot-based strategies
        # Each timestamp becomes a "snapshot" containing all markets
        timestamp_groups = defaultdict(list)
        for snap in ts_data:
            timestamp_groups[snap["timestamp"]].append(snap)

        # Run each strategy using the BacktestingEngine with enhanced data
        results = {}
        start_date = datetime.fromisoformat(ts_data[0]["timestamp"])
        end_date = datetime.fromisoformat(ts_data[-1]["timestamp"])

        strategies = [
            (StrategyType.MOMENTUM, {"momentum_threshold": 0.03}),
            (StrategyType.STATISTICAL, {"z_threshold": 1.2}),
            (StrategyType.MEAN_REVERSION, {"low_threshold": 0.25, "high_threshold": 0.75, "volume_threshold": 1000}),
            (StrategyType.VOLUME_BREAKOUT, {"volume_threshold": 5000}),
        ]

        for strategy_type, params in strategies:
            engine = BacktestingEngine(initial_capital=self.initial_capital)

            try:
                result = await engine.run_backtest(
                    market_data=ts_data,
                    strategy_type=strategy_type,
                    start_date=start_date,
                    end_date=end_date,
                    parameters=params
                )

                # Compute per-market stats
                market_trades = defaultdict(list)
                for trade in result.trades:
                    market_trades[trade.market_question[:40]].append(trade)

                strat_name = strategy_type.value
                results[strat_name] = {
                    "total_trades": result.total_trades,
                    "win_rate": f"{result.win_rate:.1%}",
                    "total_pnl": f"${result.total_pnl:,.2f}",
                    "return_pct": f"{result.total_pnl_percent:.1%}",
                    "sharpe": f"{result.sharpe_ratio:.2f}",
                    "profit_factor": f"{result.profit_factor:.2f}",
                    "final_capital": f"${result.final_capital:,.2f}",
                    "markets_traded": len(market_trades),
                    "top_markets": sorted(
                        [(q, len(ts)) for q, ts in market_trades.items()],
                        key=lambda x: -x[1]
                    )[:5],
                }

                logger.info(f"{strat_name}: {result.total_trades} trades, {result.win_rate:.1%} win rate, PnL=${result.total_pnl:,.2f}")

            except Exception as e:
                logger.error(f"Error running {strategy_type.value} backtest: {e}")
                results[strategy_type.value] = {"error": str(e)}

        # Also run with monitoring data for comparison
        mon_data = self.load_monitoring_data()
        if mon_data:
            mon_start = datetime.fromisoformat(mon_data[0]["timestamp"])
            mon_end = datetime.fromisoformat(mon_data[-1]["timestamp"])

            for strategy_type, params in strategies[:2]:  # Just momentum and statistical for comparison
                engine = BacktestingEngine(initial_capital=self.initial_capital)
                try:
                    result = await engine.run_backtest(
                        market_data=mon_data,
                        strategy_type=strategy_type,
                        start_date=mon_start,
                        end_date=mon_end,
                        parameters=params
                    )
                    results[f"monitoring_{strategy_type.value}"] = {
                        "total_trades": result.total_trades,
                        "win_rate": f"{result.win_rate:.1%}",
                        "total_pnl": f"${result.total_pnl:,.2f}",
                        "return_pct": f"{result.total_pnl_percent:.1%}",
                        "final_capital": f"${result.final_capital:,.2f}",
                        "note": "Single-snapshot monitoring data (no time dimension)",
                    }
                except Exception as e:
                    results[f"monitoring_{strategy_type.value}"] = {"error": str(e)}

        # Data quality summary
        results["_data_quality"] = {
            "timeseries_snapshots": len(ts_data),
            "timeseries_markets": len(market_series),
            "monitoring_snapshots": len(mon_data),
            "timeframe": timeframe,
            "date_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "candles_per_market": {
                cid[:20]: len(snaps) for cid, snaps in sorted(
                    market_series.items(), key=lambda x: -len(x[1])
                )[:5]
            },
        }

        return results


async def main():
    """Main entry point for running time-series backtests."""
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    runner = TimeseriesBacktestRunner(initial_capital=1000.0)

    print("=" * 70)
    print("POLYMARKET TIME-SERIES BACKTEST")
    print("=" * 70)
    print()

    # Run with different timeframes
    for tf_name, tf_val in [("1 hour", "1h"), ("4 hour", "4h"), ("daily", "1d")]:
        print(f"\n📊 Running {tf_name} backtests...")
        results = await runner.run_timeseries_backtest(timeframe=tf_val, min_candles=3)

        if "error" in results:
            print(f"  ❌ Error: {results['error']}")
            continue

        print(f"\n{'='*60}")
        print(f"RESULTS — {tf_name} candles ({tf_val})")
        print(f"{'='*60}")

        data_quality = results.pop("_data_quality", {})
        print(f"\nData Quality:")
        print(f"  Time-series snapshots: {data_quality.get('timeseries_snapshots', 'N/A')}")
        print(f"  Markets covered: {data_quality.get('timeseries_markets', 'N/A')}")
        print(f"  Date range: {data_quality.get('date_range', 'N/A')}")

        print(f"\n{'Strategy':<30} {'Trades':>7} {'Win Rate':>9} {'PnL':>12} {'Return':>9} {'Sharpe':>7}")
        print("-" * 80)
        for strat_name, strat_data in sorted(results.items()):
            if isinstance(strat_data, dict) and "error" not in strat_data:
                print(f"{strat_name:<30} {strat_data.get('total_trades', 0):>7} "
                      f"{strat_data.get('win_rate', 'N/A'):>9} "
                      f"{strat_data.get('total_pnl', 'N/A'):>12} "
                      f"{strat_data.get('return_pct', 'N/A'):>9} "
                      f"{strat_data.get('sharpe', 'N/A'):>7}")
        
        # Save results
        output_file = f"{OUTPUT_DIR}/timeseries-backtest-results-{tf_val}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to {output_file}")

    print("\n" + "=" * 70)
    print("TIME-SERIES BACKTEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())