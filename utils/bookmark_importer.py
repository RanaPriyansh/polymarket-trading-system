#!/usr/bin/env python3
"""
Bookmark Importer for X/Twitter Bookmarks
Imports and analyzes bookmarks for Polymarket trading alpha.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookmarkImporter:
    """Imports and analyzes X/Twitter bookmarks for trading alpha."""
    
    def __init__(self, db_path: str = "/root/projects/polymarket-trading-system/data/bookmarks.db"):
        self.db_path = db_path
        self.setup_database()
        
    def setup_database(self):
        """Initialize database for bookmarks."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Bookmarks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookmarks (
                bookmark_id TEXT PRIMARY KEY,
                tweet_id TEXT,
                tweet_text TEXT,
                tweet_url TEXT,
                author_username TEXT,
                author_display_name TEXT,
                author_followers INTEGER,
                retweet_count INTEGER,
                like_count INTEGER,
                reply_count INTEGER,
                quote_count INTEGER,
                created_at TIMESTAMP,
                bookmarked_at TIMESTAMP,
                hashtags TEXT,
                mentions TEXT,
                urls TEXT,
                media_type TEXT,
                media_url TEXT,
                sentiment_score REAL,
                relevance_score REAL,
                market_references TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bookmark analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookmark_analysis (
                analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_date DATE,
                total_bookmarks INTEGER,
                avg_sentiment REAL,
                positive_count INTEGER,
                negative_count INTEGER,
                neutral_count INTEGER,
                top_hashtags TEXT,
                top_mentions TEXT,
                market_references TEXT,
                high_alpha_count INTEGER,
                analysis_notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Bookmark database initialized at {self.db_path}")
    
    def import_from_json(self, file_path: str) -> bool:
        """Import bookmarks from JSON export."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Handle different export formats
            bookmarks = []
            
            if isinstance(data, list):
                bookmarks = data
            elif isinstance(data, dict):
                if "bookmarks" in data:
                    bookmarks = data["bookmarks"]
                elif "tweets" in data:
                    bookmarks = data["tweets"]
                elif "data" in data:
                    bookmarks = data["data"]
            
            if not bookmarks:
                logger.error("No bookmarks found in file")
                return False
            
            logger.info(f"Found {len(bookmarks)} bookmarks in file")
            
            # Import bookmarks
            imported_count = 0
            for bookmark in bookmarks:
                if self._import_bookmark(bookmark):
                    imported_count += 1
            
            logger.info(f"Successfully imported {imported_count} bookmarks")
            
            # Analyze imported bookmarks
            self.analyze_bookmarks()
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing bookmarks: {e}")
            return False
    
    def _import_bookmark(self, bookmark_data: Dict) -> bool:
        """Import a single bookmark."""
        try:
            # Extract bookmark ID
            bookmark_id = bookmark_data.get("id_str") or bookmark_data.get("id") or str(hash(json.dumps(bookmark_data)))
            
            # Extract tweet data
            tweet_data = bookmark_data.get("tweet", bookmark_data)
            
            # Extract author data
            author_data = tweet_data.get("user", {}) or tweet_data.get("author", {})
            
            # Extract metrics
            metrics = tweet_data.get("metrics", {}) or tweet_data.get("public_metrics", {})
            
            # Extract entities
            entities = tweet_data.get("entities", {})
            
            # Extract hashtags
            hashtags = []
            if "hashtags" in entities:
                hashtags = [tag.get("text", "") for tag in entities["hashtags"]]
            
            # Extract mentions
            mentions = []
            if "user_mentions" in entities:
                mentions = [mention.get("screen_name", "") for mention in entities["user_mentions"]]
            
            # Extract URLs
            urls = []
            if "urls" in entities:
                urls = [url.get("expanded_url", "") for url in entities["urls"]]
            
            # Extract media
            media_type = ""
            media_url = ""
            if "media" in entities:
                media = entities["media"][0] if entities["media"] else {}
                media_type = media.get("type", "")
                media_url = media.get("media_url_https", "")
            
            # Calculate sentiment score
            tweet_text = tweet_data.get("full_text") or tweet_data.get("text", "")
            sentiment_score = self._calculate_sentiment(tweet_text)
            
            # Calculate relevance score
            relevance_score = self._calculate_relevance(tweet_text, hashtags)
            
            # Extract market references
            market_references = self._extract_market_references(tweet_text)
            
            # Parse created_at
            created_at = tweet_data.get("created_at", "")
            if created_at:
                try:
                    # Handle different date formats
                    if "T" in created_at:
                        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        created_at = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                except:
                    created_at = datetime.now()
            else:
                created_at = datetime.now()
            
            # Insert into database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO bookmarks 
                (bookmark_id, tweet_id, tweet_text, tweet_url, author_username, 
                 author_display_name, author_followers, retweet_count, like_count,
                 reply_count, quote_count, created_at, bookmarked_at, hashtags,
                 mentions, urls, media_type, media_url, sentiment_score,
                 relevance_score, market_references)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bookmark_id,
                tweet_data.get("id_str", ""),
                tweet_text,
                f"https://twitter.com/i/status/{tweet_data.get('id_str', '')}",
                author_data.get("screen_name", ""),
                author_data.get("name", ""),
                author_data.get("followers_count", 0),
                metrics.get("retweet_count", 0),
                metrics.get("favorite_count", 0),
                metrics.get("reply_count", 0),
                metrics.get("quote_count", 0),
                created_at,
                datetime.now(),
                json.dumps(hashtags),
                json.dumps(mentions),
                json.dumps(urls),
                media_type,
                media_url,
                sentiment_score,
                relevance_score,
                json.dumps(market_references)
            ))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error importing bookmark: {e}")
            return False
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score for text."""
        # Simple sentiment analysis
        positive_words = {
            "good", "great", "excellent", "positive", "bullish", "up", "rise", "gain", "profit",
            "success", "win", "victory", "optimistic", "hope", "confident", "strong", "growth",
            "increase", "improve", "recover", "rally", "boom", "soar", "surge", "breakthrough",
            "agree", "support", "like", "love", "amazing", "awesome", "fantastic", "wonderful"
        }
        
        negative_words = {
            "bad", "terrible", "negative", "bearish", "down", "fall", "loss", "crash", "fail",
            "defeat", "pessimistic", "fear", "doubt", "weak", "decline", "decrease", "worsen",
            "recession", "slump", "plunge", "collapse", "crisis", "risk", "threat", "warning",
            "disagree", "oppose", "hate", "dislike", "awful", "horrible", "terrible", "disaster"
        }
        
        # Clean text
        text = text.lower()
        words = text.split()
        
        # Count positive and negative words
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        # Calculate sentiment score (-1 to 1)
        total_words = len(words)
        if total_words == 0:
            return 0
        
        sentiment = (positive_count - negative_count) / total_words
        return max(-1, min(1, sentiment * 10))  # Scale to -1 to 1
    
    def _calculate_relevance(self, text: str, hashtags: List[str]) -> float:
        """Calculate relevance score for Polymarket trading."""
        relevance = 0.0
        
        # Prediction market keywords
        prediction_keywords = {
            "polymarket", "prediction", "bet", "odds", "forecast", "probability",
            "market", "prediction market", "betting", "wager", "gambling",
            "election", "poll", "polling", "survey", "vote", "voting",
            "interest rate", "fed", "federal reserve", "inflation", "gdp",
            "unemployment", "economy", "economic", "recession", "growth",
            "ai", "artificial intelligence", "tech", "technology", "crypto",
            "bitcoin", "ethereum", "cryptocurrency", "blockchain",
            "climate", "environment", "energy", "oil", "gas",
            "war", "peace", "conflict", "geopolitics", "sanctions",
            "sports", "championship", "tournament", "world cup", "super bowl"
        }
        
        # Check text
        text_lower = text.lower()
        for keyword in prediction_keywords:
            if keyword in text_lower:
                relevance += 0.2
        
        # Check hashtags
        for hashtag in hashtags:
            hashtag_lower = hashtag.lower()
            for keyword in prediction_keywords:
                if keyword in hashtag_lower:
                    relevance += 0.3
        
        # Normalize to 0-1
        return min(1.0, relevance)
    
    def _extract_market_references(self, text: str) -> List[str]:
        """Extract market references from text."""
        import re
        
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
    
    def analyze_bookmarks(self) -> Dict:
        """Analyze imported bookmarks for trading alpha."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all bookmarks
        cursor.execute('SELECT * FROM bookmarks')
        columns = [description[0] for description in cursor.description]
        bookmarks = []
        
        for row in cursor.fetchall():
            bookmark = dict(zip(columns, row))
            # Parse JSON fields
            if bookmark['hashtags']:
                bookmark['hashtags'] = json.loads(bookmark['hashtags'])
            if bookmark['mentions']:
                bookmark['mentions'] = json.loads(bookmark['mentions'])
            if bookmark['urls']:
                bookmark['urls'] = json.loads(bookmark['urls'])
            if bookmark['market_references']:
                bookmark['market_references'] = json.loads(bookmark['market_references'])
            bookmarks.append(bookmark)
        
        conn.close()
        
        if not bookmarks:
            return {"error": "No bookmarks found"}
        
        # Calculate metrics
        total_bookmarks = len(bookmarks)
        sentiment_scores = [b['sentiment_score'] for b in bookmarks]
        relevance_scores = [b['relevance_score'] for b in bookmarks]
        
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        
        positive_count = sum(1 for s in sentiment_scores if s > 0.1)
        negative_count = sum(1 for s in sentiment_scores if s < -0.1)
        neutral_count = total_bookmarks - positive_count - negative_count
        
        # Extract top hashtags
        all_hashtags = []
        for bookmark in bookmarks:
            if bookmark['hashtags']:
                all_hashtags.extend(bookmark['hashtags'])
        
        from collections import Counter
        hashtag_counts = Counter(all_hashtags)
        top_hashtags = hashtag_counts.most_common(10)
        
        # Extract top mentions
        all_mentions = []
        for bookmark in bookmarks:
            if bookmark['mentions']:
                all_mentions.extend(bookmark['mentions'])
        
        mention_counts = Counter(all_mentions)
        top_mentions = mention_counts.most_common(10)
        
        # Extract market references
        all_market_refs = []
        for bookmark in bookmarks:
            if bookmark['market_references']:
                all_market_refs.extend(bookmark['market_references'])
        
        market_ref_counts = Counter(all_market_refs)
        top_market_refs = market_ref_counts.most_common(10)
        
        # Identify high alpha bookmarks
        high_alpha_bookmarks = []
        for bookmark in bookmarks:
            if bookmark['relevance_score'] > 0.3 or bookmark['sentiment_score'] > 0.3 or bookmark['sentiment_score'] < -0.3:
                high_alpha_bookmarks.append(bookmark)
        
        # Create analysis record
        analysis = {
            "analysis_date": datetime.now().date().isoformat(),
            "total_bookmarks": total_bookmarks,
            "avg_sentiment": avg_sentiment,
            "avg_relevance": avg_relevance,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "top_hashtags": top_hashtags,
            "top_mentions": top_mentions,
            "top_market_references": top_market_refs,
            "high_alpha_count": len(high_alpha_bookmarks),
            "high_alpha_bookmarks": [
                {
                    "text": b['tweet_text'][:200] + "..." if len(b['tweet_text']) > 200 else b['tweet_text'],
                    "author": b['author_username'],
                    "sentiment": b['sentiment_score'],
                    "relevance": b['relevance_score'],
                    "market_references": b['market_references'][:3] if b['market_references'] else []
                }
                for b in high_alpha_bookmarks[:10]
            ]
        }
        
        # Save analysis to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bookmark_analysis 
            (analysis_date, total_bookmarks, avg_sentiment, positive_count, negative_count,
             neutral_count, top_hashtags, top_mentions, market_references, high_alpha_count, analysis_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis['analysis_date'],
            analysis['total_bookmarks'],
            analysis['avg_sentiment'],
            analysis['positive_count'],
            analysis['negative_count'],
            analysis['neutral_count'],
            json.dumps(analysis['top_hashtags']),
            json.dumps(analysis['top_mentions']),
            json.dumps(analysis['top_market_references']),
            analysis['high_alpha_count'],
            f"Analysis completed at {datetime.now().isoformat()}"
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Bookmark analysis completed: {total_bookmarks} bookmarks, {len(high_alpha_bookmarks)} high alpha")
        
        return analysis
    
    def generate_trading_signals(self) -> List[Dict]:
        """Generate trading signals from bookmark analysis."""
        analysis = self.analyze_bookmarks()
        
        if "error" in analysis:
            return []
        
        signals = []
        
        # Signal 1: Sentiment divergence
        if analysis['avg_sentiment'] > 0.3 and analysis['positive_count'] > analysis['negative_count'] * 2:
            signals.append({
                "type": "bookmark_sentiment",
                "action": "long_yes",
                "confidence": 0.6,
                "reason": f"Positive sentiment in bookmarks: {analysis['avg_sentiment']:.2f}",
                "sentiment_score": analysis['avg_sentiment'],
                "bookmark_count": analysis['total_bookmarks'],
                "timestamp": datetime.now().isoformat()
            })
        
        elif analysis['avg_sentiment'] < -0.3 and analysis['negative_count'] > analysis['positive_count'] * 2:
            signals.append({
                "type": "bookmark_sentiment",
                "action": "short_yes",
                "confidence": 0.6,
                "reason": f"Negative sentiment in bookmarks: {analysis['avg_sentiment']:.2f}",
                "sentiment_score": analysis['avg_sentiment'],
                "bookmark_count": analysis['total_bookmarks'],
                "timestamp": datetime.now().isoformat()
            })
        
        # Signal 2: Market reference concentration
        if analysis['top_market_references']:
            top_ref = analysis['top_market_references'][0]
            if top_ref[1] >= 3:  # At least 3 mentions
                signals.append({
                    "type": "bookmark_concentration",
                    "action": "research",
                    "confidence": 0.5,
                    "reason": f"Market reference concentration: '{top_ref[0]}' mentioned {top_ref[1]} times",
                    "reference": top_ref[0],
                    "count": top_ref[1],
                    "timestamp": datetime.now().isoformat()
                })
        
        # Signal 3: High alpha bookmark clusters
        if analysis['high_alpha_count'] > 5:
            signals.append({
                "type": "high_alpha_cluster",
                "action": "research",
                "confidence": 0.7,
                "reason": f"High alpha bookmark cluster: {analysis['high_alpha_count']} high-relevance bookmarks",
                "high_alpha_count": analysis['high_alpha_count'],
                "timestamp": datetime.now().isoformat()
            })
        
        return signals

def main():
    """Test the bookmark importer."""
    importer = BookmarkImporter()
    
    # Create a sample bookmark file for testing
    sample_bookmarks = [
        {
            "id_str": "1234567890",
            "full_text": "Will Bitcoin hit $100k in 2026? I think there's a 70% chance. #Polymarket #Crypto",
            "user": {"screen_name": "crypto_expert", "name": "Crypto Expert", "followers_count": 10000},
            "metrics": {"retweet_count": 50, "favorite_count": 200, "reply_count": 20, "quote_count": 10},
            "created_at": "2026-03-15T10:30:00.000Z",
            "entities": {
                "hashtags": [{"text": "Polymarket"}, {"text": "Crypto"}],
                "user_mentions": [],
                "urls": [],
                "media": []
            }
        },
        {
            "id_str": "1234567891",
            "full_text": "The Fed is likely to cut rates in March. Prediction markets show 85% probability. #Fed #InterestRates",
            "user": {"screen_name": "finance_guru", "name": "Finance Guru", "followers_count": 5000},
            "metrics": {"retweet_count": 30, "favorite_count": 150, "reply_count": 15, "quote_count": 5},
            "created_at": "2026-03-14T14:20:00.000Z",
            "entities": {
                "hashtags": [{"text": "Fed"}, {"text": "InterestRates"}],
                "user_mentions": [],
                "urls": [],
                "media": []
            }
        }
    ]
    
    # Save sample bookmarks to file
    sample_file = "/root/projects/polymarket-trading-system/data/sample_bookmarks.json"
    with open(sample_file, 'w') as f:
        json.dump(sample_bookmarks, f, indent=2)
    
    # Import bookmarks
    success = importer.import_from_json(sample_file)
    
    if success:
        print("Bookmarks imported successfully!")
        
        # Analyze bookmarks
        analysis = importer.analyze_bookmarks()
        print(f"\nBookmark Analysis:")
        print(f"Total bookmarks: {analysis['total_bookmarks']}")
        print(f"Average sentiment: {analysis['avg_sentiment']:.2f}")
        print(f"Average relevance: {analysis['avg_relevance']:.2f}")
        print(f"Positive: {analysis['positive_count']}, Negative: {analysis['negative_count']}, Neutral: {analysis['neutral_count']}")
        print(f"High alpha bookmarks: {analysis['high_alpha_count']}")
        
        # Generate trading signals
        signals = importer.generate_trading_signals()
        print(f"\nTrading signals generated: {len(signals)}")
        for signal in signals:
            print(f"  - {signal['type']}: {signal['reason']}")
    else:
        print("Failed to import bookmarks")

if __name__ == "__main__":
    main()