#!/usr/bin/env python3
"""
Backtesting Engine for Polymarket Trading Strategies
Tests trading strategies on historical data to evaluate performance.
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
import sqlite3
import numpy as np
from dataclasses import dataclass
from enum import Enum
import statistics
import pandas as pd
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StrategyType(Enum):
    MEAN_REVERSION = "mean_reversion"
    VOLUME_BREAKOUT = "volume_breakout"
    SENTIMENT_BASED = "sentiment_based"
    NEWS_BASED = "news_based"
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"
    STATISTICAL = "statistical"

@dataclass
class BacktestTrade:
    """Trade generated during backtesting."""
    market_id: str
    market_question: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: float
    pnl_percent: float
    strategy: StrategyType
    confidence: float
    
    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "strategy": self.strategy.value,
            "confidence": self.confidence
        }

@dataclass
class BacktestResult:
    """Result of a backtest."""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_pnl_percent: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_holding_period: float
    best_trade: float
    worst_trade: float
    trades: List[BacktestTrade]
    final_capital: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": self.total_pnl_percent,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_holding_period": self.avg_holding_period,
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
            "trades": [t.to_dict() for t in self.trades],
            "final_capital": self.final_capital
        }

class BacktestingEngine:
    """Backtesting engine for trading strategies."""
    
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.trades: List[BacktestTrade] = []
        self.strategies = self._initialize_strategies()
        
    def _initialize_strategies(self) -> Dict[StrategyType, Callable]:
        """Initialize trading strategies."""
        return {
            StrategyType.MEAN_REVERSION: self._mean_reversion_strategy,
            StrategyType.VOLUME_BREAKOUT: self._volume_breakout_strategy,
            StrategyType.SENTIMENT_BASED: self._sentiment_based_strategy,
            StrategyType.NEWS_BASED: self._news_based_strategy,
            StrategyType.ARBITRAGE: self._arbitrage_strategy,
            StrategyType.MOMENTUM: self._momentum_strategy,
            StrategyType.STATISTICAL: self._statistical_strategy,
        }
    
    async def run_backtest(self, 
                          market_data: List[Dict], 
                          strategy_type: StrategyType,
                          start_date: datetime,
                          end_date: datetime,
                          parameters: Dict = None) -> BacktestResult:
        """Run a backtest for a specific strategy."""
        logger.info(f"Starting backtest for {strategy_type.value} strategy")
        logger.info(f"Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"Markets: {len(market_data)}")
        
        # Reset state
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        
        # Filter data by date range
        filtered_data = []
        for market in market_data:
            # Assuming market data has timestamp
            market_time = datetime.fromisoformat(market.get("timestamp", datetime.now().isoformat()))
            if start_date <= market_time <= end_date:
                filtered_data.append(market)
        
        # Sort by timestamp
        filtered_data.sort(key=lambda x: x.get("timestamp", ""))
        
        # Run strategy
        strategy_func = self.strategies[strategy_type]
        
        for i, market_snapshot in enumerate(filtered_data):
            # Generate signals
            signals = strategy_func(market_snapshot, parameters)
            
            # Execute signals
            for signal in signals:
                self._execute_signal(signal, market_snapshot)
            
            # Update positions with current prices
            self._update_positions(market_snapshot)
            
            # Check stop losses and take profits
            self._check_exit_conditions(market_snapshot)
            
            # Progress logging
            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(filtered_data)} snapshots")
        
        # Close all remaining positions
        self._close_all_positions(filtered_data[-1] if filtered_data else {})
        
        # Calculate results
        result = self._calculate_backtest_result(strategy_type, start_date, end_date)
        
        logger.info(f"Backtest completed: {result.total_trades} trades, {result.win_rate:.1%} win rate")
        return result
    
    def _mean_reversion_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Mean reversion strategy."""
        signals = []
        
        # Extract market data
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        volume = float(market_snapshot.get("volume", 0))
        
        # Strategy parameters
        low_threshold = parameters.get("low_threshold", 0.15) if parameters else 0.15
        high_threshold = parameters.get("high_threshold", 0.85) if parameters else 0.85
        volume_threshold = parameters.get("volume_threshold", 50000) if parameters else 50000
        
        # Mean reversion signal
        if yes_price < low_threshold and volume < volume_threshold:
            signals.append({
                "action": "long_yes",
                "confidence": 0.7,
                "reason": f"Mean reversion: Yes price {yes_price:.1%} is low with low volume",
                "target_price": 0.3,
                "stop_price": 0.05
            })
        elif yes_price > high_threshold and volume < volume_threshold:
            signals.append({
                "action": "short_yes",
                "confidence": 0.7,
                "reason": f"Mean reversion: Yes price {yes_price:.1%} is high with low volume",
                "target_price": 0.7,
                "stop_price": 0.95
            })
        
        return signals
    
    def _volume_breakout_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Volume breakout strategy."""
        signals = []
        
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        volume = float(market_snapshot.get("volume", 0))
        
        # Strategy parameters
        volume_threshold = parameters.get("volume_threshold", 100000) if parameters else 100000
        
        # Volume breakout signal
        if volume > volume_threshold:
            if yes_price > 0.7:
                signals.append({
                    "action": "short_yes",
                    "confidence": 0.6,
                    "reason": f"Volume breakout: High volume ({volume:,.0f}) with high Yes price",
                    "target_price": 0.6,
                    "stop_price": 0.8
                })
            elif yes_price < 0.3:
                signals.append({
                    "action": "long_yes",
                    "confidence": 0.6,
                    "reason": f"Volume breakout: High volume ({volume:,.0f}) with low Yes price",
                    "target_price": 0.4,
                    "stop_price": 0.2
                })
        
        return signals
    
    def _sentiment_based_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Sentiment-based strategy."""
        signals = []
        
        # This would use sentiment data
        # For now, simulate with random sentiment
        import random
        sentiment_score = random.uniform(-1, 1)
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        # Strategy parameters
        sentiment_threshold = parameters.get("sentiment_threshold", 0.5) if parameters else 0.5
        
        # Sentiment signal
        if sentiment_score > sentiment_threshold and yes_price < 0.4:
            signals.append({
                "action": "long_yes",
                "confidence": 0.6,
                "reason": f"Positive sentiment ({sentiment_score:.2f}) with low Yes price",
                "target_price": 0.5,
                "stop_price": 0.3
            })
        elif sentiment_score < -sentiment_threshold and yes_price > 0.6:
            signals.append({
                "action": "short_yes",
                "confidence": 0.6,
                "reason": f"Negative sentiment ({sentiment_score:.2f}) with high Yes price",
                "target_price": 0.5,
                "stop_price": 0.7
            })
        
        return signals
    
    def _news_based_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """News-based strategy."""
        signals = []
        
        # This would use news data
        # For now, simulate with random news impact
        import random
        news_impact = random.uniform(-1, 1)
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        # Strategy parameters
        news_threshold = parameters.get("news_threshold", 0.3) if parameters else 0.3
        
        # News signal
        if news_impact > news_threshold and yes_price < 0.45:
            signals.append({
                "action": "long_yes",
                "confidence": 0.7,
                "reason": f"Positive news impact ({news_impact:.2f}) with low Yes price",
                "target_price": 0.55,
                "stop_price": 0.35
            })
        elif news_impact < -news_threshold and yes_price > 0.55:
            signals.append({
                "action": "short_yes",
                "confidence": 0.7,
                "reason": f"Negative news impact ({news_impact:.2f}) with high Yes price",
                "target_price": 0.45,
                "stop_price": 0.65
            })
        
        return signals
    
    def _arbitrage_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Arbitrage strategy."""
        signals = []
        
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        no_price = float(market_snapshot.get("no_price", 0.5))
        
        # Strategy parameters
        spread_threshold = parameters.get("spread_threshold", 0.1) if parameters else 0.1
        
        # Arbitrage signal
        spread = abs(yes_price - no_price)
        
        if spread > spread_threshold:
            # Buy the cheaper side
            if yes_price < no_price:
                signals.append({
                    "action": "long_yes",
                    "confidence": 0.5,
                    "reason": f"Arbitrage: Yes price ({yes_price:.1%}) < No price ({no_price:.1%})",
                    "target_price": yes_price + spread/2,
                    "stop_price": yes_price - spread/4
                })
            else:
                signals.append({
                    "action": "long_no",
                    "confidence": 0.5,
                    "reason": f"Arbitrage: No price ({no_price:.1%}) < Yes price ({yes_price:.1%})",
                    "target_price": no_price + spread/2,
                    "stop_price": no_price - spread/4
                })
        
        return signals
    
    def _momentum_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Momentum strategy."""
        signals = []
        
        # This would use price history
        # For now, simulate with random momentum
        import random
        momentum = random.uniform(-0.1, 0.1)
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        # Strategy parameters
        momentum_threshold = parameters.get("momentum_threshold", 0.02) if parameters else 0.02
        
        # Momentum signal
        if momentum > momentum_threshold and yes_price < 0.7:
            signals.append({
                "action": "long_yes",
                "confidence": 0.6,
                "reason": f"Positive momentum ({momentum:.3f}) with room to grow",
                "target_price": yes_price * 1.1,
                "stop_price": yes_price * 0.95
            })
        elif momentum < -momentum_threshold and yes_price > 0.3:
            signals.append({
                "action": "short_yes",
                "confidence": 0.6,
                "reason": f"Negative momentum ({momentum:.3f}) with room to fall",
                "target_price": yes_price * 0.9,
                "stop_price": yes_price * 1.05
            })
        
        return signals
    
    def _statistical_strategy(self, market_snapshot: Dict, parameters: Dict = None) -> List[Dict]:
        """Statistical strategy."""
        signals = []
        
        # This would use statistical analysis
        # For now, simulate with random statistical signal
        import random
        z_score = random.uniform(-2, 2)
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        # Strategy parameters
        z_threshold = parameters.get("z_threshold", 1.5) if parameters else 1.5
        
        # Statistical signal
        if z_score > z_threshold and yes_price > 0.6:
            signals.append({
                "action": "short_yes",
                "confidence": 0.65,
                "reason": f"Statistical: Z-score {z_score:.2f} > {z_threshold} (overbought)",
                "target_price": 0.5,
                "stop_price": yes_price * 1.1
            })
        elif z_score < -z_threshold and yes_price < 0.4:
            signals.append({
                "action": "long_yes",
                "confidence": 0.65,
                "reason": f"Statistical: Z-score {z_score:.2f} < -{z_threshold} (oversold)",
                "target_price": 0.5,
                "stop_price": yes_price * 0.9
            })
        
        return signals
    
    def _execute_signal(self, signal: Dict, market_snapshot: Dict):
        """Execute a trading signal."""
        market_id = market_snapshot.get("id", "unknown")
        market_question = market_snapshot.get("question", "Unknown Market")
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        # Check if we already have a position in this market
        if market_id in self.positions:
            return
        
        # Calculate position size (2% risk based on initial capital, not compounding)
        risk_amount = self.initial_capital * 0.02
        position_size = risk_amount / 0.1  # Assuming 10% stop loss
        
        # Create trade
        trade = BacktestTrade(
            market_id=market_id,
            market_question=market_question,
            direction=signal["action"],
            entry_price=yes_price,
            exit_price=None,
            position_size=position_size,
            entry_time=datetime.fromisoformat(market_snapshot.get("timestamp", datetime.now().isoformat())),
            exit_time=None,
            pnl=0.0,
            pnl_percent=0.0,
            strategy=StrategyType.MEAN_REVERSION,  # Would be based on actual strategy
            confidence=signal.get("confidence", 0.5)
        )
        
        # Add to positions
        self.positions[market_id] = {
            "trade": trade,
            "stop_price": signal.get("stop_price", 0.0),
            "target_price": signal.get("target_price", 1.0)
        }
        
        # Update capital — deduct cost for long, receive proceeds for short
        if signal["action"] in ["long_yes", "long_no"]:
            self.capital -= position_size * yes_price
        else:  # SHORT: receive premium for selling
            self.capital += position_size * yes_price
        
        logger.debug(f"Opened position: {market_question} ({signal['action']})")
    
    def _update_positions(self, market_snapshot: Dict):
        """Update positions with current prices."""
        market_id = market_snapshot.get("id", "unknown")
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        if market_id in self.positions:
            position = self.positions[market_id]
            trade = position["trade"]
            
            # Update current price
            if trade.direction in ["long_yes", "long_no"]:
                pnl = (yes_price - trade.entry_price) * trade.position_size
                pnl_percent = (yes_price - trade.entry_price) / trade.entry_price if trade.entry_price != 0 else 0.0
            else:  # SHORT
                pnl = (trade.entry_price - yes_price) * trade.position_size
                pnl_percent = (trade.entry_price - yes_price) / trade.entry_price if trade.entry_price != 0 else 0.0
            
            trade.pnl = pnl
            trade.pnl_percent = pnl_percent
    
    def _check_exit_conditions(self, market_snapshot: Dict):
        """Check stop loss and take profit conditions."""
        market_id = market_snapshot.get("id", "unknown")
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        if market_id not in self.positions:
            return
        
        position = self.positions[market_id]
        trade = position["trade"]
        stop_price = position["stop_price"]
        target_price = position["target_price"]
        
        # Check stop loss
        if trade.direction in ["long_yes", "long_no"]:
            if yes_price <= stop_price:
                self._close_position(market_id, yes_price, "stop_loss")
            elif yes_price >= target_price:
                self._close_position(market_id, yes_price, "take_profit")
        else:  # SHORT
            if yes_price >= stop_price:
                self._close_position(market_id, yes_price, "stop_loss")
            elif yes_price <= target_price:
                self._close_position(market_id, yes_price, "take_profit")
    
    def _close_position(self, market_id: str, exit_price: float, reason: str):
        """Close a position."""
        if market_id not in self.positions:
            return
        
        position = self.positions[market_id]
        trade = position["trade"]
        
        # Calculate final P&L
        if trade.direction in ["long_yes", "long_no"]:
            pnl = (exit_price - trade.entry_price) * trade.position_size
            pnl_percent = (exit_price - trade.entry_price) / trade.entry_price if trade.entry_price != 0 else 0.0
        else:  # SHORT
            pnl = (trade.entry_price - exit_price) * trade.position_size
            pnl_percent = (trade.entry_price - exit_price) / trade.entry_price if trade.entry_price != 0 else 0.0
        
        # Update trade
        trade.exit_price = exit_price
        trade.exit_time = datetime.now()
        trade.pnl = pnl
        trade.pnl_percent = pnl_percent
        
        # Update capital — return proceeds for long, pay to buy back for short
        if trade.direction in ["long_yes", "long_no"]:
            self.capital += trade.position_size * exit_price
        else:  # SHORT: buy back shares
            self.capital -= trade.position_size * exit_price
        
        # Add to trades list
        self.trades.append(trade)
        
        # Remove from positions
        del self.positions[market_id]
        
        logger.debug(f"Closed position: {trade.market_question} ({reason}, P&L: {pnl_percent:.1%})")
    
    def _close_all_positions(self, market_snapshot: Dict):
        """Close all remaining positions."""
        market_id = market_snapshot.get("id", "unknown")
        yes_price = float(market_snapshot.get("yes_price", 0.5))
        
        for market_id in list(self.positions.keys()):
            self._close_position(market_id, yes_price, "end_of_backtest")
    
    def _calculate_backtest_result(self, strategy_type: StrategyType, start_date: datetime, end_date: datetime) -> BacktestResult:
        """Calculate backtest results."""
        if not self.trades:
            return BacktestResult(
                strategy_name=strategy_type.value,
                start_date=start_date,
                end_date=end_date,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                avg_holding_period=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                trades=[],
                final_capital=self.initial_capital
            )
        
        # Calculate metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.pnl for t in self.trades)
        # Portfolio-level return, not average of per-trade percentages
        total_pnl_percent = total_pnl / self.initial_capital if self.initial_capital > 0 else 0
        
        avg_win = statistics.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = statistics.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0
        
        total_losing = sum(abs(t.pnl) for t in losing_trades)
        profit_factor = sum(t.pnl for t in winning_trades) / total_losing if total_losing > 0 else float('inf')
        
        # Calculate holding periods
        holding_periods = []
        for trade in self.trades:
            if trade.exit_time and trade.entry_time:
                holding_period = (trade.exit_time - trade.entry_time).total_seconds() / 3600  # hours
                holding_periods.append(holding_period)
        
        avg_holding_period = statistics.mean(holding_periods) if holding_periods else 0
        
        # Calculate Sharpe ratio
        returns = [t.pnl_percent for t in self.trades]
        if len(returns) > 1:
            sharpe = statistics.mean(returns) / statistics.stdev(returns) if statistics.stdev(returns) > 0 else 0
        else:
            sharpe = 0
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = self.initial_capital
        for trade in self.trades:
            running_total += trade.pnl
            cumulative_pnl.append(running_total)
        
        max_drawdown = 0
        peak = cumulative_pnl[0] if cumulative_pnl else self.initial_capital
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            drawdown = peak - pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Best and worst trades
        best_trade = max(self.trades, key=lambda x: x.pnl_percent).pnl_percent if self.trades else 0
        worst_trade = min(self.trades, key=lambda x: x.pnl_percent).pnl_percent if self.trades else 0
        
        return BacktestResult(
            strategy_name=strategy_type.value,
            start_date=start_date,
            end_date=end_date,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            avg_holding_period=avg_holding_period,
            best_trade=best_trade,
            worst_trade=worst_trade,
            trades=self.trades,
            final_capital=self.capital
        )

async def main():
    """Test the backtesting engine."""
    engine = BacktestingEngine(initial_capital=1000.0)
    
    # Generate mock market data
    market_data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(100):  # 100 data points
        market_data.append({
            "id": f"market_{i}",
            "question": f"Will event {i} happen?",
            "yes_price": 0.3 + (i % 10) * 0.05,
            "no_price": 0.7 - (i % 10) * 0.05,
            "volume": 50000 + (i * 1000),
            "timestamp": (base_date + timedelta(hours=i)).isoformat()
        })
    
    # Run backtest
    result = await engine.run_backtest(
        market_data=market_data,
        strategy_type=StrategyType.MEAN_REVERSION,
        start_date=base_date,
        end_date=datetime.now(),
        parameters={"low_threshold": 0.15, "high_threshold": 0.85, "volume_threshold": 50000}
    )
    
    # Print results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print(f"Strategy: {result.strategy_name}")
    print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    print(f"Total Trades: {result.total_trades}")
    print(f"Win Rate: {result.win_rate:.1%}")
    print(f"Total P&L: ${result.total_pnl:.2f}")
    print(f"Portfolio Return: {result.total_pnl_percent:.1%}")
    print(f"Final Capital: ${result.final_capital:.2f}")
    print(f"Profit Factor: {result.profit_factor:.2f}")
    print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown: ${result.max_drawdown:.2f}")
    print(f"Average Holding Period: {result.avg_holding_period:.1f} hours")
    print(f"Best Trade: {result.best_trade:.1%}")
    print(f"Worst Trade: {result.worst_trade:.1%}")
    
    # Save results
    with open("/root/projects/polymarket-trading-system/data/backtest_result.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\nResults saved to backtest_result.json")

if __name__ == "__main__":
    asyncio.run(main())