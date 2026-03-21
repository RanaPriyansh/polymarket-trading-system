# Polymarket Trading System Configuration

# API Endpoints
POLYMARKET_API = {
    "gamma": "https://gamma-api.polymarket.com",
    "clob": "https://clob.polymarket.com",
    "data": "https://data-api.polymarket.com"
}

# News APIs
NEWS_APIS = {
    "newsapi": "https://newsapi.org/v2",
    "alpha_vantage": "https://www.alphavantage.co/query",
    "finnhub": "https://finnhub.io/api/v1"
}

# Economic Data APIs
ECONOMIC_APIS = {
    "fred": "https://api.stlouisfed.org/fred",
    "world_bank": "https://api.worldbank.org/v2",
    "imf": "https://www.imf.org/external/datamapper/api/v1"
}

# Social Media APIs
SOCIAL_APIS = {
    "twitter": "https://api.twitter.com/2",
    "reddit": "https://www.reddit.com/dev/api"
}

# Trading Parameters
TRADING_CONFIG = {
    "max_position_size": 0.02,  # 2% of capital per trade
    "max_total_exposure": 0.20,  # 20% total exposure
    "stop_loss_pct": 0.10,  # 10% stop loss
    "take_profit_pct": 0.25,  # 25% take profit
    "min_volume": 1000,  # Minimum $1000 volume
    "max_spread": 0.10,  # Maximum 10% spread
    "risk_free_rate": 0.05,  # 5% risk-free rate for Sharpe
}

# Scanning Parameters
SCAN_CONFIG = {
    "volume_threshold": 50000,  # $50K
    "extreme_threshold": 0.85,  # >0.85 or <0.15
    "keywords": [
        # Geopolitical
        "central bank", "election", "conflict", "sanctions", "trade war",
        "climate policy", "migration", "NATO", "China", "Russia",
        # Economic
        "inflation", "GDP", "unemployment", "interest rate", "recession",
        "stimulus", "fiscal policy", "monetary policy",
        # Technology
        "AI regulation", "semiconductor", "quantum computing", "biotech",
        "cryptocurrency", "digital currency", "space mining",
        # Events
        "summit", "conference", "treaty", "agreement", "deal"
    ]
}

# Machine Learning
ML_CONFIG = {
    "features": [
        "price", "volume", "spread", "volatility",
        "sentiment_score", "news_volume", "economic_impact",
        "time_to_resolution", "market_age", "trader_count"
    ],
    "models": {
        "anomaly_detection": "isolation_forest",
        "price_prediction": "gradient_boosting",
        "sentiment_analysis": "transformer",
        "time_series": "prophet"
    }
}

# Monitoring
MONITOR_CONFIG = {
    "check_interval": 300,  # 5 minutes
    "alert_cooldown": 3600,  # 1 hour between alerts for same market
    "telegram_chat_id": "7364191237",
    "email_alerts": False,
    "web_dashboard_port": 8080
}

# Database
DATABASE_CONFIG = {
    "type": "postgresql",
    "host": "localhost",
    "port": 5432,
    "database": "polymarket_trading",
    "user": "trader",
    "password": "trading_password"
}

# Logging
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "/root/projects/polymarket-trading-system/logs/trading.log",
    "rotation": "1 day",
    "retention": "30 days"
}