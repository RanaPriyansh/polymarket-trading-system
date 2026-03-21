#!/usr/bin/env python3
"""
Social Sentiment Analyzer for Polymarket Trading
Analyzes social media, news, and online content for trading alpha.
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
from collections import Counter
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SocialSentimentAnalyzer:
    """Analyzes social media and news for trading signals."""
    
    def __init__(self):
        self.session = None
        self.sentiment_cache = {}
        self.trending_topics = []
        
    async def start_session(self):
        """Start aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_json(self, url: str, params: Dict = None, headers: Dict = None) -> Optional[Dict]:
        """Fetch JSON data from URL."""
        try:
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    async def analyze_news_sentiment(self, query: str, days_back: int = 7) -> Dict:
        """Analyze news sentiment for a given query."""
        # Using multiple news sources
        news_sources = [
            {"name": "newsapi", "url": "https://newsapi.org/v2/everything"},
            {"name": "bing_news", "url": "https://api.bing.microsoft.com/v7.0/news/search"},
        ]
        
        all_articles = []
        sentiment_scores = []
        
        for source in news_sources:
            try:
                if source["name"] == "newsapi":
                    params = {
                        "q": query,
                        "from": (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                        "sortBy": "relevancy",
                        "pageSize": 100,
                        "apiKey": "demo"  # Would need real API key
                    }
                    # For now, simulate with web search
                    articles = await self._search_news_web(query)
                    all_articles.extend(articles)
                    
            except Exception as e:
                logger.error(f"Error with {source['name']}: {e}")
        
        # Analyze sentiment of articles
        for article in all_articles:
            sentiment = self._analyze_text_sentiment(article.get("title", "") + " " + article.get("description", ""))
            sentiment_scores.append(sentiment)
        
        # Calculate overall sentiment
        if sentiment_scores:
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            positive_count = sum(1 for s in sentiment_scores if s > 0.1)
            negative_count = sum(1 for s in sentiment_scores if s < -0.1)
            neutral_count = len(sentiment_scores) - positive_count - negative_count
        else:
            avg_sentiment = 0
            positive_count = negative_count = neutral_count = 0
        
        return {
            "query": query,
            "total_articles": len(all_articles),
            "avg_sentiment": avg_sentiment,
            "sentiment_distribution": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count
            },
            "articles": all_articles[:10],  # Top 10 articles
            "timestamp": datetime.now().isoformat()
        }
    
    async def _search_news_web(self, query: str) -> List[Dict]:
        """Search for news using web search."""
        # This would use web_search tool in real implementation
        # For now, return mock data
        return [
            {
                "title": f"Article about {query}",
                "description": f"Recent developments regarding {query}",
                "url": f"https://example.com/news/{query.replace(' ', '-')}",
                "publishedAt": datetime.now().isoformat()
            }
        ]
    
    def _analyze_text_sentiment(self, text: str) -> float:
        """Simple sentiment analysis of text."""
        # Positive and negative word lists
        positive_words = {
            "good", "great", "excellent", "positive", "bullish", "up", "rise", "gain", "profit",
            "success", "win", "victory", "optimistic", "hope", "confident", "strong", "growth",
            "increase", "improve", "recover", "rally", "boom", "soar", "surge", "breakthrough"
        }
        
        negative_words = {
            "bad", "terrible", "negative", "bearish", "down", "fall", "loss", "crash", "fail",
            "defeat", "pessimistic", "fear", "doubt", "weak", "decline", "decrease", "worsen",
            "recession", "slump", "plunge", "collapse", "crisis", "risk", "threat", "warning"
        }
        
        # Clean text
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        
        # Count positive and negative words
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Calculate sentiment score (-1 to 1)
        total_words = len(words)
        if total_words == 0:
            return 0
        
        sentiment = (positive_count - negative_count) / total_words
        return max(-1, min(1, sentiment * 10))  # Scale to -1 to 1
    
    async def analyze_social_media_trends(self, keywords: List[str]) -> Dict:
        """Analyze social media trends for keywords."""
        # This would connect to social media APIs
        # For now, simulate with web search
        
        trends = {}
        
        for keyword in keywords:
            # Search for recent social media mentions
            mentions = await self._search_social_mentions(keyword)
            
            # Analyze sentiment
            sentiment = self._analyze_text_sentiment(" ".join([m.get("text", "") for m in mentions]))
            
            # Calculate trend score
            trend_score = len(mentions) * (1 + abs(sentiment))
            
            trends[keyword] = {
                "mentions": len(mentions),
                "sentiment": sentiment,
                "trend_score": trend_score,
                "recent_posts": mentions[:5],
                "timestamp": datetime.now().isoformat()
            }
        
        # Sort by trend score
        sorted_trends = sorted(trends.items(), key=lambda x: x[1]["trend_score"], reverse=True)
        
        return {
            "total_keywords": len(keywords),
            "trends": dict(sorted_trends),
            "top_trending": [k for k, v in sorted_trends[:5]],
            "timestamp": datetime.now().isoformat()
        }
    
    async def _search_social_mentions(self, keyword: str) -> List[Dict]:
        """Search for social media mentions of keyword."""
        # This would use social media APIs
        # For now, return mock data
        return [
            {
                "text": f"People are talking about {keyword}",
                "platform": "twitter",
                "author": "user123",
                "timestamp": datetime.now().isoformat()
            }
        ]
    
    def generate_trading_signals_from_sentiment(self, sentiment_data: Dict, market_data: Dict) -> List[Dict]:
        """Generate trading signals based on sentiment analysis."""
        signals = []
        
        # Extract sentiment metrics
        avg_sentiment = sentiment_data.get("avg_sentiment", 0)
        positive_ratio = sentiment_data.get("sentiment_distribution", {}).get("positive", 0) / max(1, sentiment_data.get("total_articles", 1))
        
        # Market data
        market_question = market_data.get("question", "")
        yes_price = float(market_data.get("yes_price", 0.5))
        
        # Generate signals based on sentiment vs price
        if avg_sentiment > 0.3 and positive_ratio > 0.6 and yes_price < 0.4:
            # Positive sentiment but low price - potential buy opportunity
            signals.append({
                "type": "sentiment_divergence",
                "action": "long_yes",
                "confidence": min(0.8, abs(avg_sentiment) * 2),
                "reason": f"Positive sentiment ({avg_sentiment:.2f}) but low Yes price ({yes_price:.1%})",
                "sentiment_score": avg_sentiment,
                "price": yes_price,
                "timestamp": datetime.now().isoformat()
            })
        
        elif avg_sentiment < -0.3 and positive_ratio < 0.4 and yes_price > 0.6:
            # Negative sentiment but high price - potential sell opportunity
            signals.append({
                "type": "sentiment_divergence",
                "action": "short_yes",
                "confidence": min(0.8, abs(avg_sentiment) * 2),
                "reason": f"Negative sentiment ({avg_sentiment:.2f}) but high Yes price ({yes_price:.1%})",
                "sentiment_score": avg_sentiment,
                "price": yes_price,
                "timestamp": datetime.now().isoformat()
            })
        
        # Sentiment momentum signal
        if abs(avg_sentiment) > 0.5:
            signals.append({
                "type": "sentiment_momentum",
                "action": "long_yes" if avg_sentiment > 0 else "short_yes",
                "confidence": 0.6,
                "reason": f"Strong sentiment momentum: {avg_sentiment:.2f}",
                "sentiment_score": avg_sentiment,
                "timestamp": datetime.now().isoformat()
            })
        
        return signals
    
    async def monitor_polymarket_related_content(self) -> Dict:
        """Monitor social media and news for Polymarket-related content."""
        polymarket_keywords = [
            "polymarket", "prediction market", "betting odds", "election odds",
            "forecast", "probability", "market prediction", "odds maker"
        ]
        
        results = {}
        
        for keyword in polymarket_keywords:
            # Search for mentions
            mentions = await self._search_social_mentions(keyword)
            
            # Extract market references
            market_refs = self._extract_market_references(mentions)
            
            results[keyword] = {
                "mentions": len(mentions),
                "market_references": market_refs,
                "recent_posts": mentions[:3],
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "total_keywords": len(polymarket_keywords),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def _extract_market_references(self, mentions: List[Dict]) -> List[str]:
        """Extract market references from social media mentions."""
        market_refs = []
        
        for mention in mentions:
            text = mention.get("text", "")
            
            # Look for market-like patterns
            # Pattern 1: "Will X happen?" style questions
            will_pattern = r"Will\s+.+\?"
            will_matches = re.findall(will_pattern, text, re.IGNORECASE)
            market_refs.extend(will_matches)
            
            # Pattern 2: Percentage predictions
            percent_pattern = r"\d+%.*(?:chance|probability|odds)"
            percent_matches = re.findall(percent_pattern, text, re.IGNORECASE)
            market_refs.extend(percent_matches)
            
            # Pattern 3: Market tickers or symbols
            ticker_pattern = r"\$[A-Z]{1,5}"
            ticker_matches = re.findall(ticker_pattern, text)
            market_refs.extend(ticker_matches)
        
        return list(set(market_refs))  # Remove duplicates

class BookmarkAnalyzer:
    """Analyzes X/Twitter bookmarks for trading alpha."""
    
    def __init__(self, bookmark_file: Optional[str] = None):
        self.bookmark_file = bookmark_file
        self.bookmarks = []
        
    def load_bookmarks_from_file(self, file_path: str) -> bool:
        """Load bookmarks from exported file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Handle different export formats
            if isinstance(data, list):
                self.bookmarks = data
            elif isinstance(data, dict) and "bookmarks" in data:
                self.bookmarks = data["bookmarks"]
            else:
                logger.error("Unknown bookmark format")
                return False
            
            logger.info(f"Loaded {len(self.bookmarks)} bookmarks from {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading bookmarks: {e}")
            return False
    
    def analyze_bookmarks_for_alpha(self) -> Dict:
        """Analyze bookmarks for trading alpha."""
        if not self.bookmarks:
            return {"error": "No bookmarks loaded"}
        
        # Extract text content
        all_text = []
        for bookmark in self.bookmarks:
            if isinstance(bookmark, dict):
                text = bookmark.get("text", "") or bookmark.get("full_text", "")
                all_text.append(text)
        
        # Analyze sentiment
        sentiment_analyzer = SocialSentimentAnalyzer()
        sentiments = [sentiment_analyzer._analyze_text_sentiment(text) for text in all_text]
        
        # Extract topics
        topics = self._extract_topics(all_text)
        
        # Extract market references
        market_refs = []
        for text in all_text:
            refs = self._extract_market_references_from_text(text)
            market_refs.extend(refs)
        
        # Calculate metrics
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
        positive_count = sum(1 for s in sentiments if s > 0.1)
        negative_count = sum(1 for s in sentiments if s < -0.1)
        
        return {
            "total_bookmarks": len(self.bookmarks),
            "avg_sentiment": avg_sentiment,
            "sentiment_distribution": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": len(sentiments) - positive_count - negative_count
            },
            "top_topics": topics[:10],
            "market_references": list(set(market_refs)),
            "bookmarks_with_high_alpha": self._identify_high_alpha_bookmarks(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _extract_topics(self, texts: List[str]) -> List[Tuple[str, int]]:
        """Extract topics from text content."""
        # Simple keyword extraction
        all_words = []
        for text in texts:
            words = re.findall(r'\b\w+\b', text.lower())
            # Filter common words
            filtered_words = [w for w in words if len(w) > 3 and w not in {
                "this", "that", "with", "have", "will", "from", "they", "been", "were",
                "said", "each", "which", "their", "time", "about", "would", "there",
                "could", "other", "more", "very", "what", "know", "just", "first",
                "also", "after", "back", "year", "people", "than", "them", "well",
                "make", "like", "into", "him", "has", "two", "more", "go", "no",
                "way", "could", "my", "than", "first", "been", "call", "who",
                "its", "now", "find", "long", "down", "day", "did", "get", "come",
                "made", "find", "part", "over", "new", "sound", "take", "only",
                "little", "work", "place", "year", "live", "me", "back", "give",
                "most", "very", "after", "thing", "our", "just", "name", "good",
                "sentence", "man", "think", "say", "great", "where", "help",
                "through", "much", "before", "line", "right", "too", "mean",
                "old", "any", "same", "tell", "boy", "follow", "came", "want",
                "show", "also", "around", "form", "three", "small", "set", "put",
                "end", "does", "another", "well", "large", "must", "big", "even",
                "such", "because", "turn", "here", "why", "ask", "went", "men",
                "read", "need", "land", "different", "home", "move", "try",
                "kind", "hand", "picture", "again", "change", "off", "play",
                "place", "near", "still", "point", "mother", "world", "own",
                "should", "found", "answer", "school", "grow", "study", "learn",
                "america", "earth", "father", "head", "story", "thought", "city",
                "tree", "cross", "hard", "start", "might", "story", "saw", "far",
                "sea", "draw", "left", "late", "run", "don't", "while", "press",
                "close", "night", "real", "life", "few", "north", "open", "seem",
                "together", "next", "white", "children", "begin", "got", "walk",
                "example", "ease", "paper", "group", "always", "music", "those",
                "both", "mark", "book", "letter", "until", "mile", "river", "car",
                "feet", "care", "second", "enough", "plain", "girl", "usual",
                "young", "ready", "above", "ever", "red", "list", "though",
                "feel", "talk", "bird", "soon", "body", "dog", "family",
                "direct", "pose", "leave", "song", "measure", "door", "product",
                "black", "short", "numeral", "class", "wind", "question",
                "happen", "complete", "ship", "area", "half", "rock", "order",
                "fire", "south", "problem", "piece", "told", "knew", "pass",
                "since", "top", "whole", "king", "space", "heard", "best",
                "hour", "better", "true", "during", "hundred", "remember",
                "step", "early", "hold", "west", "ground", "interest", "reach",
                "fast", "verb", "sing", "listen", "six", "table", "travel",
                "less", "morning", "ten", "simple", "several", "vowel", "toward",
                "war", "lay", "against", "pattern", "slow", "center", "love",
                "person", "money", "serve", "appear", "road", "map", "rain",
                "rule", "govern", "pull", "cold", "notice", "voice", "energy",
                "hunt", "probable", "bed", "brother", "egg", "ride", "cell",
                "believe", "perhaps", "pick", "sudden", "count", "reason", "atom",
                "world", "compare", "north", "stand", "complete", "no", "government",
                "fact", "north", "stand", "complete", "no", "government", "fact",
                "system", "program", "question", "work", "play", "run", "might",
                "call", "end", "put", "home", "read", "hand", "port", "large",
                "spell", "add", "even", "land", "here", "must", "big", "high",
                "such", "follow", "act", "why", "ask", "men", "change", "went",
                "light", "kind", "off", "need", "house", "picture", "try", "us",
                "again", "animal", "point", "mother", "world", "near", "build",
                "self", "earth", "father", "head", "stand", "own", "page",
                "should", "country", "found", "answer", "school", "grow",
                "study", "still", "learn", "plant", "cover", "food", "sun",
                "four", "between", "state", "keep", "eye", "never", "last",
                "let", "thought", "city", "tree", "cross", "farm", "hard",
                "start", "might", "story", "saw", "far", "sea", "draw", "left",
                "late", "run", "don't", "while", "press", "close", "night",
                "real", "life", "few", "north", "open", "seem", "together",
                "next", "white", "children", "begin", "got", "walk", "example",
                "ease", "paper", "group", "always", "music", "those", "both",
                "mark", "book", "letter", "until", "mile", "river", "car",
                "feet", "care", "second", "enough", "plain", "girl", "usual",
                "young", "ready", "above", "ever", "red", "list", "though",
                "feel", "talk", "bird", "soon", "body", "dog", "family",
                "direct", "pose", "leave", "song", "measure", "door", "product",
                "black", "short", "numeral", "class", "wind", "question",
                "happen", "complete", "ship", "area", "half", "rock", "order",
                "fire", "south", "problem", "piece", "told", "knew", "pass",
                "since", "top", "whole", "king", "space", "heard", "best",
                "hour", "better", "true", "during", "hundred", "remember",
                "step", "early", "hold", "west", "ground", "interest", "reach",
                "fast", "verb", "sing", "listen", "six", "table", "travel",
                "less", "morning", "ten", "simple", "several", "vowel", "toward",
                "war", "lay", "against", "pattern", "slow", "center", "love",
                "person", "money", "serve", "appear", "road", "map", "rain",
                "rule", "govern", "pull", "cold", "notice", "voice", "energy",
                "hunt", "probable", "bed", "brother", "egg", "ride", "cell",
                "believe", "perhaps", "pick", "sudden", "count", "reason", "atom"
            }]
            all_words.extend(filtered_words)
        
        # Count word frequencies
        word_counts = Counter(all_words)
        return word_counts.most_common(20)
    
    def _extract_market_references_from_text(self, text: str) -> List[str]:
        """Extract market references from text."""
        refs = []
        
        # Pattern 1: "Will X happen?" style questions
        will_pattern = r"Will\s+.+\?"
        will_matches = re.findall(will_pattern, text, re.IGNORECASE)
        refs.extend(will_matches)
        
        # Pattern 2: Percentage predictions
        percent_pattern = r"\d+%.*(?:chance|probability|odds)"
        percent_matches = re.findall(percent_pattern, text, re.IGNORECASE)
        refs.extend(percent_matches)
        
        # Pattern 3: Market tickers
        ticker_pattern = r"\$[A-Z]{1,5}"
        ticker_matches = re.findall(ticker_pattern, text)
        refs.extend(ticker_matches)
        
        # Pattern 4: Prediction market keywords
        prediction_keywords = ["bet", "wager", "odds", "forecast", "predict", "probability"]
        for keyword in prediction_keywords:
            if keyword.lower() in text.lower():
                refs.append(f"Contains keyword: {keyword}")
        
        return refs
    
    def _identify_high_alpha_bookmarks(self) -> List[Dict]:
        """Identify bookmarks with high alpha potential."""
        high_alpha = []
        
        for i, bookmark in enumerate(self.bookmarks):
            if isinstance(bookmark, dict):
                text = bookmark.get("text", "") or bookmark.get("full_text", "")
                
                # Score based on multiple factors
                score = 0
                
                # Factor 1: Contains prediction market keywords
                prediction_keywords = ["polymarket", "prediction", "bet", "odds", "forecast", "probability"]
                for keyword in prediction_keywords:
                    if keyword.lower() in text.lower():
                        score += 2
                
                # Factor 2: Contains percentage predictions
                if re.search(r"\d+%", text):
                    score += 3
                
                # Factor 3: Contains market tickers
                if re.search(r"\$[A-Z]{1,5}", text):
                    score += 2
                
                # Factor 4: Sentiment strength
                sentiment_analyzer = SocialSentimentAnalyzer()
                sentiment = sentiment_analyzer._analyze_text_sentiment(text)
                score += abs(sentiment) * 2
                
                # Factor 5: From influential accounts
                author = bookmark.get("user", {}).get("screen_name", "")
                if author and self._is_influential_account(author):
                    score += 5
                
                if score >= 5:  # Threshold for high alpha
                    high_alpha.append({
                        "bookmark_index": i,
                        "score": score,
                        "text": text[:200] + "..." if len(text) > 200 else text,
                        "author": author,
                        "timestamp": bookmark.get("created_at", "")
                    })
        
        return sorted(high_alpha, key=lambda x: x["score"], reverse=True)
    
    def _is_influential_account(self, username: str) -> bool:
        """Check if account is influential."""
        # List of influential accounts for prediction markets
        influential_accounts = {
            "Polymarket", "Kalshi", "Metaculus", "ManifoldMarkets",
            "PredictIt", "AugurProject", "GnosisPM", "Omen_",
            "NateSilver538", "FiveThirtyEight", "ElectionMaps",
            "PredictWise", "GoodJudgment", "PhilipE.Tetlock",
            "SamHarris", "PeterAttiaMD", "balajis", "naval",
            "elonmusk", "pmarca", "peterthiel", "pmarca",
            "sama", "natfriedman", "paulg", "jasonlk",
            "cdixon", "albertwenger", "bfeld", "msuster",
            "bgurley", "jaltma", "pmarca", "pmarca"
        }
        
        return username.lower() in {acc.lower() for acc in influential_accounts}

async def main():
    """Test the social sentiment analyzer."""
    analyzer = SocialSentimentAnalyzer()
    
    # Test news sentiment analysis
    print("Testing news sentiment analysis...")
    sentiment = await analyzer.analyze_news_sentiment("Polymarket prediction market", days_back=3)
    print(f"Found {sentiment['total_articles']} articles")
    print(f"Average sentiment: {sentiment['avg_sentiment']:.2f}")
    print(f"Sentiment distribution: {sentiment['sentiment_distribution']}")
    
    # Test bookmark analysis
    print("\nTesting bookmark analysis...")
    bookmark_analyzer = BookmarkAnalyzer()
    
    # Create mock bookmarks for testing
    mock_bookmarks = [
        {"text": "Will Bitcoin hit $100k in 2026? I think 70% chance", "user": {"screen_name": "crypto_expert"}},
        {"text": "Polymarket shows 85% probability of Fed rate cut in March", "user": {"screen_name": "finance_guru"}},
        {"text": "Prediction markets are undervalued on this election outcome", "user": {"screen_name": "politics_watcher"}},
        {"text": "Just placed a bet on Polymarket for AI regulation passing", "user": {"screen_name": "tech_insider"}},
        {"text": "The odds on this sports event seem mispriced", "user": {"screen_name": "sports_bettor"}}
    ]
    
    bookmark_analyzer.bookmarks = mock_bookmarks
    analysis = bookmark_analyzer.analyze_bookmarks_for_alpha()
    
    print(f"Total bookmarks analyzed: {analysis['total_bookmarks']}")
    print(f"Average sentiment: {analysis['avg_sentiment']:.2f}")
    print(f"Top topics: {analysis['top_topics'][:5]}")
    print(f"Market references: {analysis['market_references']}")
    print(f"High alpha bookmarks: {len(analysis['bookmarks_with_high_alpha'])}")

if __name__ == "__main__":
    asyncio.run(main())