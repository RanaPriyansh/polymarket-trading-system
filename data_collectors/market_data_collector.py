#!/usr/bin/env python3
"""
Market Data Collector for Polymarket Trading System
Collects market data, prices, volumes, and order books from Polymarket API.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MarketDataCollector:
    """Collects market data from Polymarket APIs."""
    
    def __init__(self, db_path: str = "/root/projects/polymarket-trading-system/data/market_data.db"):
        self.db_path = db_path
        self.session = None
        self.setup_database()
        
    def setup_database(self):
        """Initialize SQLite database for storing market data."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Markets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                id TEXT PRIMARY KEY,
                question TEXT,
                slug TEXT,
                condition_id TEXT,
                event_slug TEXT,
                event_title TEXT,
                outcomes TEXT,
                outcome_prices TEXT,
                volume REAL,
                liquidity REAL,
                status TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                resolution_date TIMESTAMP,
                raw_data TEXT
            )
        ''')
        
        # Market snapshots (time series data)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                timestamp TIMESTAMP,
                yes_price REAL,
                no_price REAL,
                volume REAL,
                liquidity REAL,
                spread REAL,
                bid_ask_data TEXT,
                FOREIGN KEY (market_id) REFERENCES markets (id)
            )
        ''')
        
        # Order book snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_book_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                token_id TEXT,
                timestamp TIMESTAMP,
                bids TEXT,
                asks TEXT,
                spread REAL,
                depth REAL,
                FOREIGN KEY (market_id) REFERENCES markets (id)
            )
        ''')
        
        # Trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                token_id TEXT,
                timestamp TIMESTAMP,
                price REAL,
                size REAL,
                side TEXT,
                FOREIGN KEY (market_id) REFERENCES markets (id)
            )
        ''')
        
        # Anomalies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                detected_at TIMESTAMP,
                anomaly_type TEXT,
                severity REAL,
                description TEXT,
                volume_at_detection REAL,
                price_at_detection REAL,
                resolved BOOLEAN DEFAULT FALSE,
                resolved_at TIMESTAMP,
                FOREIGN KEY (market_id) REFERENCES markets (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
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
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def get_all_markets(self, limit: int = 1000) -> List[Dict]:
        """Get all active markets from Polymarket."""
        url = "https://gamma-api.polymarket.com/markets"
        params = {"limit": limit, "active": True}
        
        data = await self.fetch_json(url, params)
        if not data:
            return []
        
        markets = []
        for market in data:
            try:
                # Parse outcome prices
                outcome_prices = json.loads(market.get("outcomePrices", "[]"))
                
                markets.append({
                    "id": market.get("id"),
                    "question": market.get("question", ""),
                    "slug": market.get("slug", ""),
                    "condition_id": market.get("conditionId", ""),
                    "event_slug": market.get("eventSlug", ""),
                    "event_title": market.get("eventTitle", ""),
                    "outcomes": json.loads(market.get("outcomes", "[]")),
                    "outcome_prices": outcome_prices,
                    "volume": float(market.get("volume", 0)),
                    "liquidity": float(market.get("liquidity", 0)),
                    "status": market.get("status", ""),
                    "created_at": market.get("createdDate", ""),
                    "updated_at": market.get("updatedDate", ""),
                    "resolution_date": market.get("resolutionDate", ""),
                    "raw_data": json.dumps(market)
                })
            except Exception as e:
                logger.error(f"Error parsing market {market.get('id')}: {e}")
        
        return markets
    
    async def get_market_details(self, slug: str) -> Optional[Dict]:
        """Get detailed information for a specific market."""
        url = f"https://gamma-api.polymarket.com/markets/{slug}"
        data = await self.fetch_json(url)
        return data
    
    async def get_order_book(self, token_id: str) -> Optional[Dict]:
        """Get order book for a specific token."""
        url = f"https://clob.polymarket.com/book"
        params = {"token_id": token_id}
        data = await self.fetch_json(url, params)
        return data
    
    async def get_market_trades(self, condition_id: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a market."""
        url = f"https://data-api.polymarket.com/trades"
        params = {"market": condition_id, "limit": limit}
        data = await self.fetch_json(url, params)
        return data if data else []
    
    async def get_market_history(self, condition_id: str, interval: str = "all", fidelity: int = 50) -> List[Dict]:
        """Get price history for a market."""
        url = f"https://data-api.polymarket.com/prices-history"
        params = {"market": condition_id, "interval": interval, "fidelity": fidelity}
        data = await self.fetch_json(url, params)
        return data if data else []
    
    async def search_markets(self, keyword: str) -> List[Dict]:
        """Search markets by keyword."""
        url = "https://gamma-api.polymarket.com/public-search"
        params = {"q": keyword}
        data = await self.fetch_json(url, params)
        
        if not data:
            return []
        
        markets = []
        for event in data.get("events", []):
            for market in event.get("markets", []):
                market["event_title"] = event.get("title", "")
                market["event_slug"] = event.get("slug", "")
                markets.append(market)
        
        return markets
    
    def save_markets_to_db(self, markets: List[Dict]):
        """Save markets to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for market in markets:
            cursor.execute('''
                INSERT OR REPLACE INTO markets 
                (id, question, slug, condition_id, event_slug, event_title, 
                 outcomes, outcome_prices, volume, liquidity, status, 
                 created_at, updated_at, resolution_date, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market["id"],
                market["question"],
                market["slug"],
                market["condition_id"],
                market["event_slug"],
                market["event_title"],
                json.dumps(market["outcomes"]),
                json.dumps(market["outcome_prices"]),
                market["volume"],
                market["liquidity"],
                market["status"],
                market["created_at"],
                market["updated_at"],
                market["resolution_date"],
                market["raw_data"]
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(markets)} markets to database")
    
    def save_market_snapshot(self, market_id: str, snapshot: Dict):
        """Save market snapshot to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO market_snapshots 
            (market_id, timestamp, yes_price, no_price, volume, liquidity, spread, bid_ask_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            market_id,
            datetime.now().isoformat(),
            snapshot.get("yes_price", 0),
            snapshot.get("no_price", 0),
            snapshot.get("volume", 0),
            snapshot.get("liquidity", 0),
            snapshot.get("spread", 0),
            json.dumps(snapshot.get("bid_ask", {}))
        ))
        
        conn.commit()
        conn.close()
    
    def save_order_book_snapshot(self, market_id: str, token_id: str, order_book: Dict):
        """Save order book snapshot to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO order_book_snapshots 
            (market_id, token_id, timestamp, bids, asks, spread, depth)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            market_id,
            token_id,
            datetime.now().isoformat(),
            json.dumps(order_book.get("bids", [])),
            json.dumps(order_book.get("asks", [])),
            order_book.get("spread", 0),
            order_book.get("depth", 0)
        ))
        
        conn.commit()
        conn.close()
    
    def detect_anomalies(self, market: Dict) -> List[Dict]:
        """Detect anomalies in market data."""
        anomalies = []
        
        try:
            # Parse outcome prices
            outcome_prices = market.get("outcome_prices", [])
            if not outcome_prices:
                return anomalies
            
            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5
            
            volume = market.get("volume", 0)
            
            # Low volume + extreme pricing anomaly
            if volume < 50000:  # $50K threshold
                if yes_price > 0.85 or yes_price < 0.15:
                    anomalies.append({
                        "type": "low_volume_extreme_pricing",
                        "severity": 0.8,
                        "description": f"Low volume (${volume:,.0f}) with extreme Yes price ({yes_price:.3f})",
                        "volume": volume,
                        "price": yes_price
                    })
                
                if no_price > 0.85 or no_price < 0.15:
                    anomalies.append({
                        "type": "low_volume_extreme_pricing",
                        "severity": 0.8,
                        "description": f"Low volume (${volume:,.0f}) with extreme No price ({no_price:.3f})",
                        "volume": volume,
                        "price": no_price
                    })
            
            # Zero volume anomaly
            if volume == 0:
                anomalies.append({
                    "type": "zero_volume",
                    "severity": 0.9,
                    "description": "Market has zero trading volume",
                    "volume": 0,
                    "price": yes_price
                })
            
            # Wide spread anomaly (would need order book data)
            # This is a placeholder for spread analysis
            
        except Exception as e:
            logger.error(f"Error detecting anomalies for market {market.get('id')}: {e}")
        
        return anomalies
    
    def save_anomalies(self, market_id: str, anomalies: List[Dict]):
        """Save detected anomalies to database."""
        if not anomalies:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for anomaly in anomalies:
            cursor.execute('''
                INSERT INTO anomalies 
                (market_id, detected_at, anomaly_type, severity, description, 
                 volume_at_detection, price_at_detection)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                market_id,
                datetime.now().isoformat(),
                anomaly["type"],
                anomaly["severity"],
                anomaly["description"],
                anomaly["volume"],
                anomaly["price"]
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved {len(anomalies)} anomalies for market {market_id}")
    
    async def collect_market_data(self):
        """Main method to collect market data."""
        await self.start_session()
        
        try:
            # Get all markets
            logger.info("Collecting all markets...")
            markets = await self.get_all_markets()
            logger.info(f"Found {len(markets)} active markets")
            
            # Save to database
            self.save_markets_to_db(markets)
            
            # Analyze each market
            for market in markets:
                # Detect anomalies
                anomalies = self.detect_anomalies(market)
                if anomalies:
                    self.save_anomalies(market["id"], anomalies)
                
                # Get order book for Yes token
                if market.get("condition_id"):
                    order_book = await self.get_order_book(market["condition_id"])
                    if order_book:
                        self.save_order_book_snapshot(
                            market["id"], 
                            market["condition_id"], 
                            order_book
                        )
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            logger.info("Market data collection completed")
            
        except Exception as e:
            logger.error(f"Error in market data collection: {e}")
        finally:
            await self.close_session()
    
    async def continuous_collection(self, interval_minutes: int = 5):
        """Continuously collect market data at specified interval."""
        logger.info(f"Starting continuous collection every {interval_minutes} minutes")
        
        while True:
            try:
                await self.collect_market_data()
                logger.info(f"Sleeping for {interval_minutes} minutes...")
                await asyncio.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                logger.info("Stopping continuous collection")
                break
            except Exception as e:
                logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying


async def main():
    """Main function for testing."""
    collector = MarketDataCollector()
    
    # Test single collection
    await collector.collect_market_data()
    
    # Print summary
    conn = sqlite3.connect(collector.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM markets")
    market_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM anomalies WHERE resolved = 0")
    anomaly_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM market_snapshots")
    snapshot_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\nCollection Summary:")
    print(f"Markets in database: {market_count}")
    print(f"Active anomalies: {anomaly_count}")
    print(f"Market snapshots: {snapshot_count}")


if __name__ == "__main__":
    asyncio.run(main())