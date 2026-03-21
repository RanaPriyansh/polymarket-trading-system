#!/usr/bin/env python3
"""
News Aggregator for Polymarket Trading
Aggregates news from multiple sources for trading alpha.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
import re
from dataclasses import dataclass
from enum import Enum
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NewsCategory(Enum):
    POLITICAL = "political"
    ECONOMIC = "economic"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    FINANCIAL = "financial"
    SOCIAL = "social"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"

@dataclass
class NewsArticle:
    """News article data structure."""
    title: str
    description: str
    url: str
    source: str
    published_at: datetime
    category: NewsCategory
    relevance_score: float
    sentiment_score: float
    market_impact: str
    keywords: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "category": self.category.value,
            "relevance_score": self.relevance_score,
            "sentiment_score": self.sentiment_score,
            "market_impact": self.market_impact,
            "keywords": self.keywords
        }

class NewsAggregator:
    """Aggregates news from multiple sources for Polymarket trading."""
    
    def __init__(self):
        self.session = None
        self.articles_cache = {}
        self.news_sources = self._initialize_news_sources()
        
    def _initialize_news_sources(self) -> Dict[str, Dict]:
        """Initialize news sources configuration."""
        return {
            "reuters": {
                "name": "Reuters",
                "url": "https://www.reuters.com",
                "category": NewsCategory.FINANCIAL,
                "weight": 1.0
            },
            "bloomberg": {
                "name": "Bloomberg",
                "url": "https://www.bloomberg.com",
                "category": NewsCategory.FINANCIAL,
                "weight": 1.0
            },
            "cnbc": {
                "name": "CNBC",
                "url": "https://www.cnbc.com",
                "category": NewsCategory.FINANCIAL,
                "weight": 0.9
            },
            "bbc": {
                "name": "BBC News",
                "url": "https://www.bbc.com/news",
                "category": NewsCategory.POLITICAL,
                "weight": 0.9
            },
            "cnn": {
                "name": "CNN",
                "url": "https://www.cnn.com",
                "category": NewsCategory.POLITICAL,
                "weight": 0.8
            },
            "techcrunch": {
                "name": "TechCrunch",
                "url": "https://techcrunch.com",
                "category": NewsCategory.TECHNOLOGY,
                "weight": 0.8
            },
            "arstechnica": {
                "name": "Ars Technica",
                "url": "https://arstechnica.com",
                "category": NewsCategory.TECHNOLOGY,
                "weight": 0.7
            },
            "polymarket_blog": {
                "name": "Polymarket Blog",
                "url": "https://polymarket.com/blog",
                "category": NewsCategory.FINANCIAL,
                "weight": 1.2
            }
        }
    
    async def start_session(self):
        """Start aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_news(self, keywords: List[str], days_back: int = 7, max_articles: int = 100) -> List[NewsArticle]:
        """Fetch news articles based on keywords."""
        await self.start_session()
        
        all_articles = []
        
        try:
            for source_name, source_config in self.news_sources.items():
                try:
                    articles = await self._fetch_from_source(source_name, source_config, keywords, days_back)
                    all_articles.extend(articles)
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error fetching from {source_name}: {e}")
            
            # Sort by relevance score
            all_articles.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # Limit results
            return all_articles[:max_articles]
            
        except Exception as e:
            logger.error(f"Error in fetch_news: {e}")
            return []
        finally:
            await self.close_session()
    
    async def _fetch_from_source(self, source_name: str, source_config: Dict, keywords: List[str], days_back: int) -> List[NewsArticle]:
        """Fetch news from a specific source."""
        # This would implement actual fetching from each source
        # For now, return mock data
        
        articles = []
        
        # Simulate fetching based on keywords
        for keyword in keywords:
            # Create mock article
            article = NewsArticle(
                title=f"News about {keyword} from {source_config['name']}",
                description=f"Recent developments regarding {keyword} affecting markets",
                url=f"{source_config['url']}/article/{keyword.replace(' ', '-')}",
                source=source_config['name'],
                published_at=datetime.now() - timedelta(hours=len(articles)),
                category=source_config['category'],
                relevance_score=self._calculate_relevance(keyword, keywords),
                sentiment_score=self._analyze_sentiment(f"{keyword} market impact"),
                market_impact=self._assess_market_impact(keyword),
                keywords=[keyword]
            )
            articles.append(article)
        
        return articles
    
    def _calculate_relevance(self, keyword: str, all_keywords: List[str]) -> float:
        """Calculate relevance score for a keyword."""
        # Base relevance
        relevance = 0.5
        
        # Boost for prediction market keywords
        prediction_keywords = ["polymarket", "prediction", "bet", "odds", "forecast", "probability"]
        for pk in prediction_keywords:
            if pk.lower() in keyword.lower():
                relevance += 0.3
        
        # Boost for market-moving keywords
        market_keywords = ["election", "fed", "interest rate", "inflation", "gdp", "unemployment", "war", "peace", "sanctions", "tariff"]
        for mk in market_keywords:
            if mk.lower() in keyword.lower():
                relevance += 0.2
        
        # Normalize to 0-1
        return min(1.0, relevance)
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text."""
        # Simple sentiment analysis
        positive_words = {"good", "great", "positive", "bullish", "up", "rise", "gain", "profit", "success", "win", "optimistic"}
        negative_words = {"bad", "terrible", "negative", "bearish", "down", "fall", "loss", "crash", "fail", "pessimistic"}
        
        words = set(text.lower().split())
        positive_count = len(words.intersection(positive_words))
        negative_count = len(words.intersection(negative_words))
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)
    
    def _assess_market_impact(self, keyword: str) -> str:
        """Assess potential market impact of keyword."""
        high_impact_keywords = {
            "election", "fed", "interest rate", "inflation", "gdp", "unemployment",
            "war", "peace", "sanctions", "tariff", "crash", "rally", "surge", "plunge"
        }
        
        medium_impact_keywords = {
            "regulation", "policy", "announcement", "decision", "report", "data",
            "forecast", "prediction", "analysis", "outlook"
        }
        
        keyword_lower = keyword.lower()
        
        for high_word in high_impact_keywords:
            if high_word in keyword_lower:
                return "high"
        
        for medium_word in medium_impact_keywords:
            if medium_word in keyword_lower:
                return "medium"
        
        return "low"
    
    async def aggregate_polymarket_news(self) -> Dict:
        """Aggregate news specifically relevant to Polymarket."""
        # Define Polymarket-specific keywords
        polymarket_keywords = [
            "Polymarket", "prediction market", "betting odds", "election odds",
            "Fed interest rate", "inflation data", "GDP report", "unemployment",
            "geopolitical", "sanctions", "trade war", "AI regulation",
            "cryptocurrency", "Bitcoin", "Ethereum", "climate policy",
            "election 2024", "election 2028", "presidential election",
            "supreme court", "congress", "senate", "house",
            "FDA approval", "clinical trial", "vaccine", "pandemic",
            "space launch", "mars mission", "moon landing",
            "sports championship", "world cup", "super bowl"
        ]
        
        # Fetch news
        articles = await self.fetch_news(polymarket_keywords, days_back=3, max_articles=50)
        
        # Analyze articles
        analysis = self._analyze_articles(articles)
        
        # Generate trading signals
        signals = self._generate_signals_from_news(articles)
        
        return {
            "total_articles": len(articles),
            "articles_by_category": analysis["by_category"],
            "articles_by_impact": analysis["by_impact"],
            "top_keywords": analysis["top_keywords"],
            "trading_signals": signals,
            "timestamp": datetime.now().isoformat()
        }
    
    def _analyze_articles(self, articles: List[NewsArticle]) -> Dict:
        """Analyze articles for patterns and insights."""
        by_category = {}
        by_impact = {"high": 0, "medium": 0, "low": 0}
        keyword_counts = {}
        
        for article in articles:
            # Count by category
            category = article.category.value
            by_category[category] = by_category.get(category, 0) + 1
            
            # Count by impact
            by_impact[article.market_impact] = by_impact.get(article.market_impact, 0) + 1
            
            # Count keywords
            for keyword in article.keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        # Sort keywords by count
        top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "by_category": by_category,
            "by_impact": by_impact,
            "top_keywords": top_keywords
        }
    
    def _generate_signals_from_news(self, articles: List[NewsArticle]) -> List[Dict]:
        """Generate trading signals from news articles."""
        signals = []
        
        # Group articles by market impact
        high_impact_articles = [a for a in articles if a.market_impact == "high"]
        medium_impact_articles = [a for a in articles if a.market_impact == "medium"]
        
        # Generate signals based on high impact news
        for article in high_impact_articles:
            if article.sentiment_score > 0.3:
                signals.append({
                    "type": "news_sentiment",
                    "action": "long_yes",
                    "confidence": min(0.8, article.relevance_score * 0.8),
                    "reason": f"High impact positive news: {article.title[:50]}...",
                    "source": article.source,
                    "sentiment": article.sentiment_score,
                    "impact": article.market_impact,
                    "timestamp": datetime.now().isoformat()
                })
            elif article.sentiment_score < -0.3:
                signals.append({
                    "type": "news_sentiment",
                    "action": "short_yes",
                    "confidence": min(0.8, article.relevance_score * 0.8),
                    "reason": f"High impact negative news: {article.title[:50]}...",
                    "source": article.source,
                    "sentiment": article.sentiment_score,
                    "impact": article.market_impact,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Generate consensus signals from multiple sources
        if len(high_impact_articles) >= 3:
            avg_sentiment = sum(a.sentiment_score for a in high_impact_articles) / len(high_impact_articles)
            if abs(avg_sentiment) > 0.2:
                signals.append({
                    "type": "news_consensus",
                    "action": "long_yes" if avg_sentiment > 0 else "short_yes",
                    "confidence": 0.7,
                    "reason": f"Consensus from {len(high_impact_articles)} high impact articles: {avg_sentiment:.2f}",
                    "sentiment": avg_sentiment,
                    "article_count": len(high_impact_articles),
                    "timestamp": datetime.now().isoformat()
                })
        
        return signals

class EconomicCalendar:
    """Tracks economic events and data releases."""
    
    def __init__(self):
        self.events = []
        self.event_sources = self._initialize_event_sources()
    
    def _initialize_event_sources(self) -> Dict[str, Dict]:
        """Initialize economic event sources."""
        return {
            "fred": {
                "name": "Federal Reserve Economic Data",
                "url": "https://fred.stlouisfed.org",
                "events": ["FOMC Meeting", "Interest Rate Decision", "CPI Release", "GDP Release"]
            },
            "bls": {
                "name": "Bureau of Labor Statistics",
                "url": "https://www.bls.gov",
                "events": ["Employment Situation", "Unemployment Rate", "CPI Release"]
            },
            "bea": {
                "name": "Bureau of Economic Analysis",
                "url": "https://www.bea.gov",
                "events": ["GDP Release", "Personal Income", "Trade Balance"]
            },
            "ecb": {
                "name": "European Central Bank",
                "url": "https://www.ecb.europa.eu",
                "events": ["ECB Meeting", "Interest Rate Decision"]
            },
            "boj": {
                "name": "Bank of Japan",
                "url": "https://www.boj.or.jp",
                "events": ["BOJ Meeting", "Interest Rate Decision"]
            }
        }
    
    async def get_upcoming_events(self, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming economic events."""
        # This would fetch from economic calendar APIs
        # For now, return mock data
        
        events = []
        base_date = datetime.now()
        
        # Generate mock events
        event_types = [
            {"name": "FOMC Meeting", "impact": "high", "currency": "USD"},
            {"name": "CPI Release", "impact": "high", "currency": "USD"},
            {"name": "GDP Release", "impact": "high", "currency": "USD"},
            {"name": "Employment Situation", "impact": "high", "currency": "USD"},
            {"name": "ECB Meeting", "impact": "medium", "currency": "EUR"},
            {"name": "BOJ Meeting", "impact": "medium", "currency": "JPY"},
            {"name": "Retail Sales", "impact": "medium", "currency": "USD"},
            {"name": "Industrial Production", "impact": "medium", "currency": "USD"},
            {"name": "Consumer Confidence", "impact": "medium", "currency": "USD"},
            {"name": "Housing Starts", "impact": "low", "currency": "USD"}
        ]
        
        for i in range(10):  # Generate 10 mock events
            event = event_types[i % len(event_types)]
            event_date = base_date + timedelta(days=i*3)
            
            events.append({
                "name": event["name"],
                "date": event_date.isoformat(),
                "impact": event["impact"],
                "currency": event["currency"],
                "forecast": "N/A",
                "previous": "N/A",
                "actual": None,
                "source": "Mock Data"
            })
        
        return events
    
    def analyze_event_impact(self, event: Dict, market_data: Dict) -> Dict:
        """Analyze the potential impact of an economic event on a market."""
        market_question = market_data.get("question", "").lower()
        event_name = event["name"].lower()
        
        impact_score = 0
        reasoning = []
        
        # Check for direct impact
        if "interest rate" in event_name and "interest rate" in market_question:
            impact_score += 0.8
            reasoning.append("Direct impact on interest rate market")
        
        if "inflation" in event_name and "inflation" in market_question:
            impact_score += 0.8
            reasoning.append("Direct impact on inflation market")
        
        if "gdp" in event_name and "gdp" in market_question:
            impact_score += 0.8
            reasoning.append("Direct impact on GDP market")
        
        if "employment" in event_name and "unemployment" in market_question:
            impact_score += 0.8
            reasoning.append("Direct impact on unemployment market")
        
        # Check for indirect impact
        if "election" in market_question and event["impact"] == "high":
            impact_score += 0.3
            reasoning.append("High impact event may affect election sentiment")
        
        # Normalize score
        impact_score = min(1.0, impact_score)
        
        return {
            "event": event["name"],
            "market": market_data.get("question", ""),
            "impact_score": impact_score,
            "reasoning": reasoning,
            "event_date": event["date"],
            "event_impact": event["impact"]
        }

async def main():
    """Test the news aggregator."""
    aggregator = NewsAggregator()
    
    print("Testing news aggregation for Polymarket...")
    result = await aggregator.aggregate_polymarket_news()
    
    print(f"\nNews Aggregation Results:")
    print(f"Total articles: {result['total_articles']}")
    print(f"Articles by category: {result['articles_by_category']}")
    print(f"Articles by impact: {result['articles_by_impact']}")
    print(f"Top keywords: {result['top_keywords'][:5]}")
    print(f"Trading signals generated: {len(result['trading_signals'])}")
    
    # Test economic calendar
    print("\n\nTesting economic calendar...")
    calendar = EconomicCalendar()
    events = await calendar.get_upcoming_events(days_ahead=14)
    
    print(f"Upcoming economic events (next 14 days):")
    for event in events[:5]:
        print(f"  - {event['name']} ({event['date'][:10]}) - Impact: {event['impact']}")

if __name__ == "__main__":
    asyncio.run(main())