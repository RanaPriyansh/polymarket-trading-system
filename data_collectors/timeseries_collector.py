#!/usr/bin/env python3
"""
Time-Series Data Collector for Polymarket Trading System

Collects historical trade data from Polymarket's data API and builds
time-series price snapshots suitable for backtesting.

Data Sources:
1. Polymarket data-api trades endpoint (paginable recent trades)
2. Periodic monitoring snapshots (ongoing collection)

The trades API returns up to 500 trades per request with timestamp,
price, and size. We aggregate these into time-binned OHLCV candles.
"""

import asyncio
import aiohttp
import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import statistics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "/root/projects/polymarket-trading-system/data/timeseries.db"
GAMMA_API = "https://gamma-api.polymarket.com/markets"
DATA_API = "https://data-api.polymarket.com/trades"


class TimeseriesCollector:
    """Collects and stores time-series price data from Polymarket."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.session = None
        self.setup_database()

    def setup_database(self):
        """Initialize SQLite database for time-series data."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Price candles (OHLCV) at various timeframes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                condition_id TEXT NOT NULL,
                slug TEXT,
                question TEXT,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume REAL,
                trade_count INTEGER,
                liquidity REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(market_id, timeframe, timestamp)
            )
        ''')

        # Raw trades for granular analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                slug TEXT,
                outcome TEXT,
                outcome_index INTEGER,
                side TEXT,
                price REAL,
                size REAL,
                timestamp INTEGER NOT NULL,
                trade_hash TEXT,
                market_id TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trade_hash)
            )
        ''')

        # Market snapshots from periodic monitoring
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                condition_id TEXT,
                slug TEXT,
                question TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                yes_price REAL,
                no_price REAL,
                volume REAL,
                liquidity REAL,
                spread REAL,
                outcome_prices TEXT,
                source TEXT DEFAULT 'monitoring',
                UNIQUE(market_id, timestamp)
            )
        ''')

        # Indexes for fast queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_candles_market_time ON price_candles(market_id, timeframe, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_candles_condition ON price_candles(condition_id, timeframe, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_condition ON raw_trades(condition_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_market ON market_snapshots(market_id, timestamp)')

        conn.commit()
        conn.close()
        logger.info(f"Time-series database initialized at {self.db_path}")

    async def start_session(self):
        """Start aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_json(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Fetch JSON data from URL."""
        try:
            async with self.session.get(url, params=params,
                                         timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_active_markets(self, min_volume: float = 10000,
                                  limit: int = 200) -> List[Dict]:
        """Get active markets with minimum volume for time-series collection."""
        all_markets = []
        offset = 0
        batch_size = min(limit, 100)

        while True:
            params = {
                "limit": batch_size,
                "active": "true",
                "order": "volume",
                "ascending": "false",
                "offset": offset
            }

            data = await self.fetch_json(GAMMA_API, params)
            if not data:
                break

            for market in data:
                try:
                    volume = float(market.get("volume", 0) or 0)
                    if volume < min_volume:
                        continue

                    outcome_prices = json.loads(market.get("outcomePrices", "[]"))
                    clob_token_ids = json.loads(market.get("clobTokenIds", "[]"))

                    all_markets.append({
                        "id": market.get("id"),
                        "question": market.get("question", ""),
                        "slug": market.get("slug", ""),
                        "condition_id": market.get("conditionId", ""),
                        "clob_token_ids": clob_token_ids,
                        "outcomes": json.loads(market.get("outcomes", "[]")),
                        "outcome_prices": outcome_prices,
                        "volume": volume,
                        "liquidity": float(market.get("liquidity", 0) or 0),
                        "one_week_price_change": float(market.get("oneWeekPriceChange", 0) or 0),
                        "one_month_price_change": float(market.get("oneMonthPriceChange", 0) or 0),
                    })
                except Exception as e:
                    logger.error(f"Error parsing market: {e}")
                    continue

            if len(data) < batch_size:
                break
            offset += batch_size
            if offset >= limit:
                break

            await asyncio.sleep(0.2)

        logger.info(f"Found {len(all_markets)} active markets with volume >= ${min_volume:,.0f}")
        return all_markets

    async def collect_trades_for_market(self, condition_id: str, slug: str = "",
                                         max_trades: int = 1000) -> List[Dict]:
        """Collect recent trades for a single market from data-api."""
        all_trades = []
        seen_hashes = set()
        limit_per_request = 500

        for attempt in range(3):  # Max 3 pagination requests
            url = f"{DATA_API}?market={condition_id}&limit={limit_per_request}"
            if attempt > 0:
                # Use after_timestamp to try getting different ranges
                pass

            data = await self.fetch_json(url)
            if not data:
                break

            for trade in data:
                trade_hash = trade.get("transactionHash", "")
                if trade_hash and trade_hash in seen_hashes:
                    continue
                seen_hashes.add(trade_hash) if trade_hash else seen_hashes.add(
                    f"{trade.get('timestamp', '')}-{trade.get('price', '')}"
                )

                all_trades.append({
                    "condition_id": condition_id,
                    "slug": slug or trade.get("slug", ""),
                    "outcome": trade.get("outcome", ""),
                    "outcome_index": trade.get("outcomeIndex", 0),
                    "side": trade.get("side", ""),
                    "price": float(trade.get("price", 0)),
                    "size": float(trade.get("size", 0)),
                    "timestamp": int(trade.get("timestamp", 0)),
                    "trade_hash": trade_hash,
                    "market_id": trade.get("title", ""),
                })

            if len(data) < limit_per_request:
                break

            # Polymarket data-api doesn't support proper pagination for older trades
            # We get what we can
            break

        return all_trades

    def save_trades(self, trades: List[Dict]):
        """Save raw trades to database."""
        if not trades:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        saved = 0
        for trade in trades:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO raw_trades
                    (condition_id, slug, outcome, outcome_index, side, price,
                     size, timestamp, trade_hash, market_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade["condition_id"],
                    trade["slug"],
                    trade["outcome"],
                    trade["outcome_index"],
                    trade["side"],
                    trade["price"],
                    trade["size"],
                    trade["timestamp"],
                    trade["trade_hash"],
                    trade["market_id"],
                ))
                saved += cursor.rowcount
            except Exception as e:
                logger.error(f"Error saving trade: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Saved {saved} new trades to database")

    def save_snapshot(self, market: Dict):
        """Save a market snapshot to the time-series database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        outcome_prices = market.get("outcome_prices", [])
        yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO market_snapshots
                (market_id, condition_id, slug, question, timestamp,
                 yes_price, no_price, volume, liquidity, spread, outcome_prices, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market.get("id", ""),
                market.get("condition_id", ""),
                market.get("slug", ""),
                market.get("question", ""),
                datetime.now().isoformat(),
                yes_price,
                no_price,
                market.get("volume", 0),
                market.get("liquidity", 0),
                abs(yes_price - no_price),
                json.dumps(outcome_prices),
                "monitoring",
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
        finally:
            conn.close()

    def aggregate_trades_to_candles(self, condition_id: str = None,
                                      timeframe_minutes: int = 60) -> int:
        """Aggregate raw trades into OHLCV candles.

        Args:
            condition_id: If specified, only aggregate for this market
            timeframe_minutes: Candle timeframe in minutes (default 60 = 1h)

        Returns:
            Number of candles created
        """
        timeframe_seconds = timeframe_minutes * 60
        if timeframe_minutes < 60:
            timeframe_str = f"{timeframe_minutes}m"
        elif timeframe_minutes < 1440:
            timeframe_str = f"{timeframe_minutes // 60}h"
        else:
            timeframe_str = f"{timeframe_minutes // 1440}d"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get trades grouped by condition_id
        if condition_id:
            cursor.execute('''
                SELECT condition_id, slug, timestamp, price, size
                FROM raw_trades
                WHERE condition_id = ?
                ORDER BY condition_id, timestamp
            ''', (condition_id,))
        else:
            cursor.execute('''
                SELECT condition_id, slug, timestamp, price, size
                FROM raw_trades
                ORDER BY condition_id, timestamp
            ''')

        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return 0

        # Group trades by (condition_id, candle_start)
        candles = defaultdict(lambda: {
            "prices": [], "sizes": [], "timestamps": [],
            "slug": "", "slugs": set()
        })

        for condition_id_val, slug, timestamp, price, size in rows:
            candle_start = (timestamp // timeframe_seconds) * timeframe_seconds
            key = (condition_id_val, candle_start)
            candles[key]["prices"].append(price)
            candles[key]["sizes"].append(size)
            candles[key]["timestamps"].append(timestamp)
            candles[key]["slug"] = slug or ""
            candles[key]["slugs"].add(slug or "")
            candles[key]["condition_id"] = condition_id_val

        # Insert candles
        candles_created = 0
        for (condition_id_val, candle_start), data in candles.items():
            if not data["prices"]:
                continue

            open_price = data["prices"][0]
            close_price = data["prices"][-1]
            high_price = max(data["prices"])
            low_price = min(data["prices"])
            volume = sum(data["sizes"])
            trade_count = len(data["prices"])
            slug = data["slug"] or list(data["slugs"])[0] if data["slugs"] else ""

            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO price_candles
                    (market_id, condition_id, slug, question, timeframe,
                     timestamp, open_price, high_price, low_price, close_price,
                     volume, trade_count, liquidity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    condition_id_val,  # using condition_id as market_id for now
                    condition_id_val,
                    slug,
                    "",  # question not in trades data
                    timeframe_str,
                    candle_start,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    trade_count,
                    0,  # liquidity not available from trades
                ))
                candles_created += 1
            except Exception as e:
                logger.error(f"Error inserting candle: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Created {candles_created} {timeframe_str} candles from {len(rows)} trades")
        return candles_created

    def build_backtest_dataset(self, min_trades: int = 5,
                                timeframe_minutes: int = 60,
                                condition_ids: List[str] = None) -> List[Dict]:
        """Build a backtest-ready dataset from time-series data.

        Returns a list of market snapshots with OHLCV data, sorted by timestamp.
        Each snapshot is compatible with the existing BacktestingEngine.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        timeframe_seconds = timeframe_minutes * 60

        # Get markets with enough data
        if condition_ids:
            placeholders = ','.join(['?'] * len(condition_ids))
            cursor.execute(f'''
                SELECT condition_id, COUNT(*) as trade_count,
                       MIN(timestamp) as first_trade, MAX(timestamp) as last_trade,
                       AVG(price) as avg_price
                FROM raw_trades
                WHERE condition_id IN ({placeholders})
                GROUP BY condition_id
                HAVING trade_count >= ?
                ORDER BY trade_count DESC
            ''', (*condition_ids, min_trades))
        else:
            cursor.execute('''
                SELECT condition_id, COUNT(*) as trade_count,
                       MIN(timestamp) as first_trade, MAX(timestamp) as last_trade,
                       AVG(price) as avg_price
                FROM raw_trades
                GROUP BY condition_id
                HAVING trade_count >= ?
                ORDER BY trade_count DESC
            ''', (min_trades,))

        market_stats = cursor.fetchall()

        if not market_stats:
            # Fall back to market_snapshots
            logger.info("No trade data available, using market snapshots")
            cursor.execute('''
                SELECT market_id, condition_id, slug, question,
                       yes_price, no_price, volume, liquidity, timestamp
                FROM market_snapshots
                ORDER BY timestamp ASC
            ''')
            snapshots = cursor.fetchall()
            conn.close()

            return [
                {
                    "id": s[0],
                    "condition_id": s[1],
                    "slug": s[2],
                    "question": s[3],
                    "yes_price": s[4],
                    "no_price": s[5],
                    "volume": s[6],
                    "liquidity": s[7],
                    "timestamp": s[8],
                }
                for s in snapshots
            ]

        # Build OHLCV-annotated snapshots for each market
        dataset = []

        for condition_id, trade_count, first_ts, last_ts, avg_price in market_stats:
            # Get OHLCV candles for this market
            timeframe_str = f"{timeframe_minutes}m" if timeframe_minutes < 60 else f"{timeframe_minutes // 60}h"

            cursor.execute('''
                SELECT timestamp, open_price, high_price, low_price, close_price,
                       volume, trade_count, slug, condition_id
                FROM price_candles
                WHERE condition_id = ? AND timeframe = ?
                ORDER BY timestamp ASC
            ''', (condition_id, timeframe_str))

            candles = cursor.fetchall()

            for candle in candles:
                ts, open_p, high_p, low_p, close_p, vol, tc, slug, cid = candle
                dataset.append({
                    "id": cid,
                    "question": slug or cid[:20],
                    "yes_price": close_p,  # Use close price as current price
                    "no_price": 1.0 - close_p,
                    "volume": vol,
                    "liquidity": 0,  # Not available from trades
                    "timestamp": datetime.fromtimestamp(ts).isoformat(),
                    # Extra fields for enhanced strategies
                    "open_price": open_p,
                    "high_price": high_p,
                    "low_price": low_p,
                    "close_price": close_p,
                    "trade_count": tc,
                })

        conn.close()

        # Sort by timestamp
        dataset.sort(key=lambda x: x.get("timestamp", ""))

        logger.info(f"Built backtest dataset with {len(dataset)} snapshots across {len(market_stats)} markets")
        return dataset

    async def collect_timeseries_for_markets(self, markets: List[Dict],
                                               max_trades_per_market: int = 500) -> Dict:
        """Collect time-series data for a list of markets.

        Returns stats about collection: {total_trades, markets_collected, errors}
        """
        stats = {"total_trades": 0, "markets_collected": 0, "errors": 0}

        for i, market in enumerate(markets):
            condition_id = market.get("condition_id", "")
            slug = market.get("slug", "")

            if not condition_id:
                continue

            try:
                trades = await self.collect_trades_for_market(condition_id, slug)
                self.save_trades(trades)
                stats["total_trades"] += len(trades)
                stats["markets_collected"] += 1

                # Also save a current snapshot
                self.save_snapshot(market)

                logger.info(f"[{i+1}/{len(markets)}] Collected {len(trades)} trades for: {market.get('question', '')[:50]}")

            except Exception as e:
                logger.error(f"Error collecting data for {slug}: {e}")
                stats["errors"] += 1

            # Rate limiting
            await asyncio.sleep(0.3)

        return stats

    async def collect_and_build(self, min_volume: float = 50000,
                                 max_markets: int = 50,
                                 aggregate_timeframes: List[int] = [60, 240, 1440]) -> Dict:
        """Full collection pipeline: get markets, collect trades, aggregate candles.

        Args:
            min_volume: Minimum market volume to include
            max_markets: Maximum number of markets to process
            aggregate_timeframes: Timeframes in minutes for candle aggregation

        Returns:
            Collection stats and dataset summary
        """
        await self.start_session()
        try:
            # Step 1: Get active markets
            markets = await self.get_active_markets(min_volume=min_volume)
            markets = markets[:max_markets]

            if not markets:
                logger.warning("No active markets found")
                return {"total_trades": 0, "markets_collected": 0, "errors": 0}

            # Step 2: Collect trades
            stats = await self.collect_timeseries_for_markets(markets)

            # Step 3: Aggregate into candles
            for tf in aggregate_timeframes:
                candles = self.aggregate_trades_to_candles(timeframe_minutes=tf)
                stats[f"candles_{tf}m"] = candles

            # Step 4: Build backtest dataset
            condition_ids = [m.get("condition_id") for m in markets if m.get("condition_id")]
            dataset = self.build_backtest_dataset(
                min_trades=3,
                timeframe_minutes=60,
                condition_ids=condition_ids if condition_ids else None
            )
            stats["dataset_size"] = len(dataset)

            return stats

        finally:
            await self.close_session()

    def get_collection_stats(self) -> Dict:
        """Get current database statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM raw_trades")
        total_trades = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT condition_id) FROM raw_trades")
        unique_markets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM market_snapshots")
        total_snapshots = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT market_id) FROM market_snapshots")
        snapshot_markets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM price_candles")
        total_candles = cursor.fetchone()[0]

        cursor.execute("""
            SELECT timeframe, COUNT(*) FROM price_candles
            GROUP BY timeframe
        """)
        candle_counts = dict(cursor.fetchall())

        cursor.execute("""
            SELECT condition_id, MIN(timestamp), MAX(timestamp)
            FROM raw_trades
            GROUP BY condition_id
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)
        market_date_ranges = cursor.fetchall()

        conn.close()

        return {
            "total_trades": total_trades,
            "unique_markets": unique_markets,
            "total_snapshots": total_snapshots,
            "snapshot_markets": snapshot_markets,
            "total_candles": total_candles,
            "candle_counts": candle_counts,
            "top_markets": [
                {"condition_id": m[0][:20], "first_ts": m[1], "last_ts": m[2]}
                for m in market_date_ranges
            ],
        }


async def main():
    """Main function for running the time-series collector."""
    collector = TimeseriesCollector()

    print("=" * 70)
    print("POLYMARKET TIME-SERIES DATA COLLECTOR")
    print("=" * 70)

    # Collect data
    print("\n📊 Collecting time-series data from Polymarket...")
    stats = await collector.collect_and_build(
        min_volume=50000,    # Only markets with $50K+ volume
        max_markets=50,      # Top 50 markets
        aggregate_timeframes=[60, 240, 1440]  # 1h, 4h, 1d candles
    )

    print(f"\n📈 Collection Results:")
    print(f"  Total trades collected: {stats.get('total_trades', 0)}")
    print(f"  Markets collected: {stats.get('markets_collected', 0)}")
    print(f"  Errors: {stats.get('errors', 0)}")
    for key in sorted(stats.keys()):
        if key.startswith("candles_"):
            print(f"  {key}: {stats[key]}")
    print(f"  Backtest dataset size: {stats.get('dataset_size', 0)}")

    # Print database stats
    db_stats = collector.get_collection_stats()
    print(f"\n💾 Database Stats:")
    print(f"  Total trades: {db_stats['total_trades']}")
    print(f"  Unique markets: {db_stats['unique_markets']}")
    print(f"  Total snapshots: {db_stats['total_snapshots']}")
    print(f"  Total candles: {db_stats['total_candles']}")
    print(f"  Candle breakdown: {db_stats['candle_counts']}")


if __name__ == "__main__":
    asyncio.run(main())