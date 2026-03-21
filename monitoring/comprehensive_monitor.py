#!/usr/bin/env python3
"""
Comprehensive Polymarket Monitor
Monitors 50+ markets for trading opportunities.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveMarketMonitor:
    """Monitors multiple Polymarket markets for opportunities."""
    
    def __init__(self):
        self.session = None
        self.markets = {}
        self.alerts = []
        
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
        params = {"limit": limit, "active": "true"}
        
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
    
    def analyze_market(self, market: Dict) -> Dict:
        """Analyze a market for trading opportunities."""
        analysis = {
            "market": market["question"],
            "slug": market["slug"],
            "volume": market["volume"],
            "liquidity": market["liquidity"],
            "opportunities": [],
            "risk_level": "low",
            "potential_return": 0.0
        }
        
        try:
            # Parse outcome prices
            outcome_prices = market.get("outcome_prices", [])
            if not outcome_prices:
                return analysis
            
            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 1.0 - yes_price
            
            # Calculate spread
            spread = abs(yes_price - no_price)
            
            # Opportunity detection
            opportunities = []
            
            # 1. Low volume + extreme pricing
            if market["volume"] < 50000:  # $50K threshold
                if yes_price > 0.85:
                    opportunities.append({
                        "type": "short_yes",
                        "reason": f"High Yes price ({yes_price:.1%}) with low volume (${market['volume']:,.0f})",
                        "confidence": 0.7,
                        "potential_return": min(0.2, yes_price - 0.7)  # Expect price to drop to 70%
                    })
                elif yes_price < 0.15:
                    opportunities.append({
                        "type": "long_yes",
                        "reason": f"Low Yes price ({yes_price:.1%}) with low volume (${market['volume']:,.0f})",
                        "confidence": 0.6,
                        "potential_return": min(0.3, 0.3 - yes_price)  # Expect price to rise to 30%
                    })
            
            # 2. High volume with mispricing
            if market["volume"] > 100000:  # $100K threshold
                if yes_price > 0.9:
                    opportunities.append({
                        "type": "short_yes",
                        "reason": f"Very high Yes price ({yes_price:.1%}) with high volume",
                        "confidence": 0.8,
                        "potential_return": min(0.15, yes_price - 0.75)  # Expect price to drop to 75%
                    })
                elif yes_price < 0.1:
                    opportunities.append({
                        "type": "long_yes",
                        "reason": f"Very low Yes price ({yes_price:.1%}) with high volume",
                        "confidence": 0.7,
                        "potential_return": min(0.25, 0.25 - yes_price)  # Expect price to rise to 25%
                    })
            
            # 3. Wide spread opportunity
            if spread > 0.05:  # 5% spread
                opportunities.append({
                    "type": "arbitrage",
                    "reason": f"Wide spread ({spread:.1%}) between Yes/No",
                    "confidence": 0.5,
                    "potential_return": spread * 0.3  # Capture 30% of spread
                })
            
            # 4. Volume spike detection
            if market["volume"] > 500000:  # $500K threshold
                opportunities.append({
                    "type": "volume_spike",
                    "reason": f"High volume (${market['volume']:,.0f}) indicates market interest",
                    "confidence": 0.6,
                    "potential_return": 0.1  # 10% potential return
                })
            
            # Update analysis
            analysis["opportunities"] = opportunities
            analysis["yes_price"] = yes_price
            analysis["no_price"] = no_price
            analysis["spread"] = spread
            
            # Calculate risk level
            if len(opportunities) > 0:
                avg_confidence = sum(o["confidence"] for o in opportunities) / len(opportunities)
                if avg_confidence > 0.7:
                    analysis["risk_level"] = "low"
                elif avg_confidence > 0.5:
                    analysis["risk_level"] = "medium"
                else:
                    analysis["risk_level"] = "high"
            
            # Calculate potential return
            if len(opportunities) > 0:
                analysis["potential_return"] = sum(o["potential_return"] for o in opportunities)
            
        except Exception as e:
            logger.error(f"Error analyzing market {market['slug']}: {e}")
        
        return analysis
    
    async def monitor_markets(self, max_markets: int = 100):
        """Monitor markets for trading opportunities."""
        await self.start_session()
        
        try:
            # Get all markets
            logger.info(f"Fetching up to {max_markets} markets...")
            markets = await self.get_all_markets(limit=max_markets)
            logger.info(f"Found {len(markets)} active markets")
            
            # Analyze each market
            all_analyses = []
            for i, market in enumerate(markets, 1):
                if i % 20 == 0:
                    logger.info(f"Analyzing market {i}/{len(markets)}...")
                
                analysis = self.analyze_market(market)
                if analysis["opportunities"]:
                    all_analyses.append(analysis)
            
            # Sort by potential return
            all_analyses.sort(key=lambda x: x["potential_return"], reverse=True)
            
            # Print results
            print("\n" + "="*80)
            print("COMPREHENSIVE POLYMARKET MONITOR - TOP OPPORTUNITIES")
            print("="*80)
            
            for i, analysis in enumerate(all_analyses[:20], 1):  # Top 20
                print(f"\n{i}. {analysis['market']}")
                print(f"   Volume: ${analysis['volume']:,.0f} | Yes: {analysis.get('yes_price', 0):.1%} | No: {analysis.get('no_price', 0):.1%}")
                print(f"   Risk: {analysis['risk_level']} | Potential Return: {analysis['potential_return']:.1%}")
                
                for opp in analysis["opportunities"]:
                    print(f"   - {opp['type'].upper()}: {opp['reason']} (Confidence: {opp['confidence']:.0%})")
            
            # Summary
            print(f"\n\nSUMMARY:")
            print(f"Total markets analyzed: {len(markets)}")
            print(f"Markets with opportunities: {len(all_analyses)}")
            print(f"Total potential return: {sum(a['potential_return'] for a in all_analyses):.1%}")
            
            # Save to file
            self.save_results(all_analyses)
            
        except Exception as e:
            logger.error(f"Error in monitor_markets: {e}")
        finally:
            await self.close_session()
    
    def save_results(self, analyses: List[Dict]):
        """Save results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/root/projects/polymarket-trading-system/data/monitor_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_markets": len(analyses),
                "analyses": analyses
            }, f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        
        # Also save to database
        self.save_to_database(analyses)
    
    def save_to_database(self, analyses: List[Dict]):
        """Save results to SQLite database."""
        db_path = "/root/projects/polymarket-trading-system/data/monitoring.db"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitoring_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                market_slug TEXT,
                market_question TEXT,
                volume REAL,
                yes_price REAL,
                no_price REAL,
                spread REAL,
                risk_level TEXT,
                potential_return REAL,
                opportunities TEXT
            )
        ''')
        
        # Insert results
        for analysis in analyses:
            cursor.execute('''
                INSERT INTO monitoring_results 
                (timestamp, market_slug, market_question, volume, yes_price, no_price, 
                 spread, risk_level, potential_return, opportunities)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now().isoformat(),
                analysis["slug"],
                analysis["market"],
                analysis["volume"],
                analysis.get("yes_price", 0),
                analysis.get("no_price", 0),
                analysis.get("spread", 0),
                analysis["risk_level"],
                analysis["potential_return"],
                json.dumps(analysis["opportunities"])
            ))
        
        conn.commit()
        conn.close()
        logger.info(f"Results saved to database")


async def main():
    """Main function."""
    monitor = ComprehensiveMarketMonitor()
    
    print("Starting comprehensive Polymarket monitor...")
    print("This will analyze 100+ markets for trading opportunities.")
    print("Unlike the old system that only monitored 3 markets.")
    print()
    
    await monitor.monitor_markets(max_markets=100)


if __name__ == "__main__":
    asyncio.run(main())