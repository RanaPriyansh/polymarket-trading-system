#!/usr/bin/env python3
"""
Polymarket Signal Generator
Generates trading signals for multiple markets based on various strategies.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SignalGenerator:
    """Generates trading signals for Polymarket markets."""
    
    def __init__(self):
        self.session = None
        self.markets = {}
        
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
    
    async def get_market_data(self, slug: str) -> Optional[Dict]:
        """Get market data for a specific market."""
        url = f"https://gamma-api.polymarket.com/markets?slug={slug}"
        data = await self.fetch_json(url)
        if data and len(data) > 0:
            return data[0]
        return None
    
    async def get_order_book(self, token_id: str) -> Optional[Dict]:
        """Get order book for a token."""
        url = f"https://clob.polymarket.com/book"
        params = {"token_id": token_id}
        data = await self.fetch_json(url, params)
        return data
    
    async def get_market_history(self, condition_id: str, interval: str = "all", fidelity: int = 50) -> List[Dict]:
        """Get price history for a market."""
        url = f"https://data-api.polymarket.com/prices-history"
        params = {"market": condition_id, "interval": interval, "fidelity": fidelity}
        data = await self.fetch_json(url, params)
        return data if data else []
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI for a list of prices."""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_momentum(self, prices: List[float], period: int = 10) -> float:
        """Calculate price momentum."""
        if len(prices) < period:
            return 0.0
        
        current_price = prices[-1]
        past_price = prices[-period]
        
        if past_price == 0:
            return 0.0
        
        momentum = (current_price - past_price) / past_price
        return momentum
    
    def detect_trend(self, prices: List[float], short_period: int = 5, long_period: int = 20) -> str:
        """Detect price trend."""
        if len(prices) < long_period:
            return "neutral"
        
        short_avg = np.mean(prices[-short_period:])
        long_avg = np.mean(prices[-long_period:])
        
        if short_avg > long_avg * 1.02:  # 2% above
            return "bullish"
        elif short_avg < long_avg * 0.98:  # 2% below
            return "bearish"
        else:
            return "neutral"
    
    def generate_signals(self, market_data: Dict, order_book: Optional[Dict] = None) -> List[Dict]:
        """Generate trading signals for a market."""
        signals = []
        
        try:
            # Parse market data
            question = market_data.get("question", "")
            slug = market_data.get("slug", "")
            condition_id = market_data.get("conditionId", "")
            
            # Parse outcome prices
            outcome_prices_str = market_data.get("outcomePrices", "[]")
            if isinstance(outcome_prices_str, str):
                outcome_prices = json.loads(outcome_prices_str)
            else:
                outcome_prices = outcome_prices_str
            
            if not outcome_prices or len(outcome_prices) < 2:
                return signals
            
            yes_price = float(outcome_prices[0])
            no_price = float(outcome_prices[1])
            volume = float(market_data.get("volume", 0))
            liquidity = float(market_data.get("liquidity", 0))
            
            # Signal 1: Mean Reversion
            if yes_price > 0.85:
                signals.append({
                    "type": "mean_reversion",
                    "action": "short_yes",
                    "strength": min(0.9, (yes_price - 0.7) / 0.3),  # Stronger signal if price is higher
                    "reason": f"Yes price {yes_price:.1%} is high, expect reversion",
                    "target_price": 0.7,
                    "stop_price": yes_price + 0.1,
                    "confidence": 0.7
                })
            elif yes_price < 0.15:
                signals.append({
                    "type": "mean_reversion",
                    "action": "long_yes",
                    "strength": min(0.9, (0.3 - yes_price) / 0.3),
                    "reason": f"Yes price {yes_price:.1%} is low, expect reversion",
                    "target_price": 0.3,
                    "stop_price": max(0.01, yes_price - 0.1),
                    "confidence": 0.6
                })
            
            # Signal 2: Volume-based
            if volume > 500000:  # $500K volume
                if yes_price > 0.8:
                    signals.append({
                        "type": "volume_breakout",
                        "action": "short_yes",
                        "strength": 0.8,
                        "reason": f"High volume (${volume:,.0f}) with high Yes price",
                        "target_price": 0.65,
                        "stop_price": yes_price + 0.05,
                        "confidence": 0.6
                    })
                elif yes_price < 0.2:
                    signals.append({
                        "type": "volume_breakout",
                        "action": "long_yes",
                        "strength": 0.7,
                        "reason": f"High volume (${volume:,.0f}) with low Yes price",
                        "target_price": 0.35,
                        "stop_price": max(0.01, yes_price - 0.05),
                        "confidence": 0.6
                    })
            
            # Signal 3: Spread arbitrage
            spread = abs(yes_price - no_price)
            if spread > 0.1:  # 10% spread
                signals.append({
                    "type": "arbitrage",
                    "action": "capture_spread",
                    "strength": min(0.8, spread),
                    "reason": f"Wide spread {spread:.1%} between Yes/No",
                    "target_price": yes_price - spread/2,
                    "stop_price": yes_price + spread/4,
                    "confidence": 0.5
                })
            
            # Signal 4: Order book analysis
            if order_book:
                # Analyze bid/ask imbalance
                bids = order_book.get("bids", [])
                asks = order_book.get("asks", [])
                
                if bids and asks:
                    # Calculate bid/ask ratio
                    total_bid_size = sum(b.get("size", 0) for b in bids[:5])
                    total_ask_size = sum(a.get("size", 0) for a in asks[:5])
                    
                    if total_bid_size > total_ask_size * 2:  # Bids much larger than asks
                        signals.append({
                            "type": "order_book_imbalance",
                            "action": "long_yes",
                            "strength": 0.6,
                            "reason": f"Bid size ({total_bid_size:.0f}) >> Ask size ({total_ask_size:.0f})",
                            "target_price": yes_price * 1.1,
                            "stop_price": yes_price * 0.9,
                            "confidence": 0.5
                        })
                    elif total_ask_size > total_bid_size * 2:  # Asks much larger than bids
                        signals.append({
                            "type": "order_book_imbalance",
                            "action": "short_yes",
                            "strength": 0.6,
                            "reason": f"Ask size ({total_ask_size:.0f}) >> Bid size ({total_bid_size:.0f})",
                            "target_price": yes_price * 0.9,
                            "stop_price": yes_price * 1.1,
                            "confidence": 0.5
                        })
            
            # Signal 5: Liquidity-based
            if liquidity > 0 and volume > 0:
                volume_liquidity_ratio = volume / liquidity
                if volume_liquidity_ratio > 10:  # High volume relative to liquidity
                    signals.append({
                        "type": "liquidity_signal",
                        "action": "caution",
                        "strength": 0.3,
                        "reason": f"High volume/liquidity ratio ({volume_liquidity_ratio:.1f})",
                        "target_price": None,
                        "stop_price": None,
                        "confidence": 0.3
                    })
            
            # Add metadata to signals
            for signal in signals:
                signal.update({
                    "market": question,
                    "slug": slug,
                    "condition_id": condition_id,
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume": volume,
                    "liquidity": liquidity,
                    "timestamp": datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error generating signals for market: {e}")
        
        return signals
    
    async def analyze_market(self, slug: str) -> List[Dict]:
        """Analyze a single market and generate signals."""
        # Get market data
        market_data = await self.get_market_data(slug)
        if not market_data:
            return []
        
        # Get order book if we have token IDs
        order_book = None
        outcome_prices_str = market_data.get("outcomePrices", "[]")
        if isinstance(outcome_prices_str, str):
            outcome_prices = json.loads(outcome_prices_str)
        else:
            outcome_prices = outcome_prices_str
        
        if outcome_prices and len(outcome_prices) >= 2:
            # Try to get order book for Yes token
            # This is a simplified approach - in reality we'd need token IDs
            pass
        
        # Generate signals
        signals = self.generate_signals(market_data, order_book)
        
        return signals
    
    async def scan_multiple_markets(self, market_slugs: List[str]) -> Dict[str, List[Dict]]:
        """Scan multiple markets for signals."""
        await self.start_session()
        
        all_signals = {}
        
        try:
            for i, slug in enumerate(market_slugs, 1):
                if i % 10 == 0:
                    logger.info(f"Analyzing market {i}/{len(market_slugs)}: {slug}")
                
                signals = await self.analyze_market(slug)
                if signals:
                    all_signals[slug] = signals
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            # Print summary
            print("\n" + "="*80)
            print("POLYMARKET SIGNAL GENERATOR - RESULTS")
            print("="*80)
            
            total_signals = 0
            for slug, signals in all_signals.items():
                if signals:
                    market_name = signals[0].get("market", slug)
                    print(f"\n{market_name}")
                    print(f"  Volume: ${signals[0].get('volume', 0):,.0f}")
                    print(f"  Yes Price: {signals[0].get('yes_price', 0):.1%}")
                    print(f"  No Price: {signals[0].get('no_price', 0):.1%}")
                    
                    for signal in signals:
                        total_signals += 1
                        print(f"  - {signal['type'].upper()}: {signal['action']} ({signal['reason']})")
                        if signal.get('target_price'):
                            print(f"    Target: {signal['target_price']:.1%} | Stop: {signal['stop_price']:.1%}")
            
            print(f"\n\nTOTAL SIGNALS: {total_signals}")
            print(f"MARKETS WITH SIGNALS: {len(all_signals)}")
            
            # Save results
            self.save_signals(all_signals)
            
        except Exception as e:
            logger.error(f"Error in scan_multiple_markets: {e}")
        finally:
            await self.close_session()
        
        return all_signals
    
    def save_signals(self, signals: Dict[str, List[Dict]]):
        """Save signals to file and database."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save to JSON file
        filename = f"/root/projects/polymarket-trading-system/data/signals_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_signals": sum(len(s) for s in signals.values()),
                "signals": signals
            }, f, indent=2)
        
        logger.info(f"Signals saved to {filename}")
        
        # Save to database
        self.save_signals_to_db(signals)
    
    def save_signals_to_db(self, signals: Dict[str, List[Dict]]):
        """Save signals to SQLite database."""
        db_path = "/root/projects/polymarket-trading-system/data/signals.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trading_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                market_slug TEXT,
                market_question TEXT,
                signal_type TEXT,
                action TEXT,
                strength REAL,
                reason TEXT,
                target_price REAL,
                stop_price REAL,
                confidence REAL,
                yes_price REAL,
                no_price REAL,
                volume REAL,
                liquidity REAL
            )
        ''')
        
        # Insert signals
        for slug, signal_list in signals.items():
            for signal in signal_list:
                cursor.execute('''
                    INSERT INTO trading_signals 
                    (timestamp, market_slug, market_question, signal_type, action, strength, 
                     reason, target_price, stop_price, confidence, yes_price, no_price, 
                     volume, liquidity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    signal.get("timestamp"),
                    signal.get("slug"),
                    signal.get("market"),
                    signal.get("type"),
                    signal.get("action"),
                    signal.get("strength"),
                    signal.get("reason"),
                    signal.get("target_price"),
                    signal.get("stop_price"),
                    signal.get("confidence"),
                    signal.get("yes_price"),
                    signal.get("no_price"),
                    signal.get("volume"),
                    signal.get("liquidity")
                ))
        
        conn.commit()
        conn.close()
        logger.info(f"Signals saved to database")


async def main():
    """Main function."""
    generator = SignalGenerator()
    
    # List of market slugs to analyze (can be expanded)
    # For now, let's use some example markets
    example_markets = [
        "will-eric-trump-win-the-2028-us-presidential-election",
        "will-the-fed-decrease-interest-rates-by-25-bps-after-the-march-2026-meeting",
        "will-there-be-no-change-in-fed-interest-rates-after-the-march-2026-meeting",
        "will-bitcoin-hit-100000-in-2026",
        "will-ethereum-hit-10000-in-2026",
        "will-donald-trump-win-the-2028-us-presidential-election",
        "will-joe-biden-run-for-president-in-2028",
        "will-elon-musk-become-trillionaire-in-2026",
        "will-ai-replace-50-of-jobs-by-2030",
        "will-china-invade-taiwan-before-2027"
    ]
    
    print("Starting Polymarket Signal Generator...")
    print(f"Analyzing {len(example_markets)} markets for trading signals...")
    print()
    
    await generator.scan_multiple_markets(example_markets)


if __name__ == "__main__":
    asyncio.run(main())