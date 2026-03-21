#!/usr/bin/env python3
"""
Polymarket Trading Utilities
Comprehensive toolkit for trading operations, risk management, and analysis.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
import numpy as np
from dataclasses import dataclass
from enum import Enum
import math

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradeDirection(Enum):
    LONG_YES = "long_yes"
    LONG_NO = "long_no"
    SHORT_YES = "short_yes"
    SHORT_NO = "short_no"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class TradingSignal:
    """Trading signal data structure."""
    market_id: str
    market_question: str
    direction: TradeDirection
    confidence: float  # 0.0 to 1.0
    risk_level: RiskLevel
    entry_price: float
    target_price: float
    stop_price: float
    position_size: float
    expected_return: float
    reasoning: str
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "risk_level": self.risk_level.value,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_price": self.stop_price,
            "position_size": self.position_size,
            "expected_return": self.expected_return,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class Position:
    """Trading position data structure."""
    market_id: str
    market_question: str
    direction: TradeDirection
    entry_price: float
    current_price: float
    position_size: float
    stop_price: float
    target_price: float
    entry_time: datetime
    pnl: float
    pnl_percent: float
    
    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "position_size": self.position_size,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "entry_time": self.entry_time.isoformat(),
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent
        }

class TradingUtils:
    """Comprehensive trading utilities."""
    
    def __init__(self, capital: float = 1000.0):
        self.capital = capital
        self.positions: Dict[str, Position] = {}
        self.trading_history: List[Dict] = []
        self.session = None
        
    async def start_session(self):
        """Start aiohttp session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    # Risk Management Functions
    
    def calculate_position_size(self, signal: TradingSignal, risk_per_trade: float = 0.02) -> float:
        """Calculate position size based on risk management rules."""
        # Maximum risk per trade (default 2% of capital)
        max_risk_amount = self.capital * risk_per_trade
        
        # Calculate risk per share
        if signal.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            risk_per_share = signal.entry_price - signal.stop_price
        else:  # SHORT
            risk_per_share = signal.stop_price - signal.entry_price
        
        if risk_per_share <= 0:
            logger.warning(f"Invalid risk per share: {risk_per_share}")
            return 0.0
        
        # Calculate position size
        position_size = max_risk_amount / abs(risk_per_share)
        
        # Apply confidence adjustment
        confidence_multiplier = 0.5 + (signal.confidence * 0.5)  # 50-100% based on confidence
        position_size *= confidence_multiplier
        
        # Apply risk level adjustment
        risk_multiplier = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.75,
            RiskLevel.HIGH: 0.5,
            RiskLevel.VERY_HIGH: 0.25
        }[signal.risk_level]
        position_size *= risk_multiplier
        
        # Ensure minimum position size
        min_position = 1.0  # $1 minimum
        max_position = self.capital * 0.1  # 10% of capital maximum
        
        return max(min_position, min(position_size, max_position))
    
    def calculate_expected_return(self, signal: TradingSignal) -> float:
        """Calculate expected return for a signal."""
        if signal.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            expected_return = (signal.target_price - signal.entry_price) / signal.entry_price
        else:  # SHORT
            expected_return = (signal.entry_price - signal.target_price) / signal.entry_price
        
        # Adjust by confidence
        return expected_return * signal.confidence
    
    def check_correlation(self, new_signal: TradingSignal) -> float:
        """Check correlation with existing positions."""
        if not self.positions:
            return 0.0
        
        # Simple correlation check based on market similarity
        correlations = []
        for position in self.positions.values():
            # Markets in same category or with similar keywords
            if self._markets_are_related(position.market_question, new_signal.market_question):
                correlations.append(1.0)  # High correlation
            else:
                correlations.append(0.0)  # Low correlation
        
        return max(correlations) if correlations else 0.0
    
    def _markets_are_related(self, market1: str, market2: str) -> bool:
        """Check if two markets are related."""
        # Simple keyword matching
        keywords1 = set(market1.lower().split())
        keywords2 = set(market2.lower().split())
        
        # Common words to ignore
        ignore_words = {"will", "the", "a", "an", "be", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with", "by"}
        
        keywords1 = keywords1 - ignore_words
        keywords2 = keywords2 - ignore_words
        
        # Check for common keywords
        common = keywords1.intersection(keywords2)
        return len(common) >= 2  # At least 2 common keywords
    
    # Market Analysis Functions
    
    def analyze_market_opportunity(self, market_data: Dict) -> List[TradingSignal]:
        """Analyze a market for trading opportunities."""
        signals = []
        
        try:
            # Parse market data
            market_id = market_data.get("id", "")
            question = market_data.get("question", "")
            outcome_prices = market_data.get("outcome_prices", [])
            volume = float(market_data.get("volume", 0))
            liquidity = float(market_data.get("liquidity", 0))
            
            if not outcome_prices or len(outcome_prices) < 2:
                return signals
            
            yes_price = float(outcome_prices[0])
            no_price = float(outcome_prices[1])
            
            # Strategy 1: Mean Reversion
            if yes_price > 0.85 and volume < 50000:
                signal = TradingSignal(
                    market_id=market_id,
                    market_question=question,
                    direction=TradeDirection.SHORT_YES,
                    confidence=0.7,
                    risk_level=RiskLevel.MEDIUM,
                    entry_price=yes_price,
                    target_price=0.7,
                    stop_price=min(0.95, yes_price + 0.1),
                    position_size=0.0,  # Will be calculated
                    expected_return=0.0,  # Will be calculated
                    reasoning=f"Mean reversion: Yes price {yes_price:.1%} is high with low volume",
                    timestamp=datetime.now()
                )
                signal.expected_return = self.calculate_expected_return(signal)
                signal.position_size = self.calculate_position_size(signal)
                signals.append(signal)
            
            elif yes_price < 0.15 and volume < 50000:
                signal = TradingSignal(
                    market_id=market_id,
                    market_question=question,
                    direction=TradeDirection.LONG_YES,
                    confidence=0.6,
                    risk_level=RiskLevel.MEDIUM,
                    entry_price=yes_price,
                    target_price=0.3,
                    stop_price=max(0.05, yes_price - 0.1),
                    position_size=0.0,
                    expected_return=0.0,
                    reasoning=f"Mean reversion: Yes price {yes_price:.1%} is low with low volume",
                    timestamp=datetime.now()
                )
                signal.expected_return = self.calculate_expected_return(signal)
                signal.position_size = self.calculate_position_size(signal)
                signals.append(signal)
            
            # Strategy 2: Volume Spike
            if volume > 100000:
                if yes_price > 0.8:
                    signal = TradingSignal(
                        market_id=market_id,
                        market_question=question,
                        direction=TradeDirection.SHORT_YES,
                        confidence=0.6,
                        risk_level=RiskLevel.LOW,
                        entry_price=yes_price,
                        target_price=0.65,
                        stop_price=min(0.9, yes_price + 0.05),
                        position_size=0.0,
                        expected_return=0.0,
                        reasoning=f"Volume spike: High volume (${volume:,.0f}) with high Yes price",
                        timestamp=datetime.now()
                    )
                    signal.expected_return = self.calculate_expected_return(signal)
                    signal.position_size = self.calculate_position_size(signal)
                    signals.append(signal)
                
                elif yes_price < 0.2:
                    signal = TradingSignal(
                        market_id=market_id,
                        market_question=question,
                        direction=TradeDirection.LONG_YES,
                        confidence=0.6,
                        risk_level=RiskLevel.LOW,
                        entry_price=yes_price,
                        target_price=0.35,
                        stop_price=max(0.1, yes_price - 0.05),
                        position_size=0.0,
                        expected_return=0.0,
                        reasoning=f"Volume spike: High volume (${volume:,.0f}) with low Yes price",
                        timestamp=datetime.now()
                    )
                    signal.expected_return = self.calculate_expected_return(signal)
                    signal.position_size = self.calculate_position_size(signal)
                    signals.append(signal)
            
            # Strategy 3: Spread Arbitrage
            spread = abs(yes_price - no_price)
            if spread > 0.1:  # 10% spread
                signal = TradingSignal(
                    market_id=market_id,
                    market_question=question,
                    direction=TradeDirection.LONG_YES if yes_price < no_price else TradeDirection.LONG_NO,
                    confidence=0.5,
                    risk_level=RiskLevel.LOW,
                    entry_price=min(yes_price, no_price),
                    target_price=min(yes_price, no_price) + spread/2,
                    stop_price=min(yes_price, no_price) - spread/4,
                    position_size=0.0,
                    expected_return=0.0,
                    reasoning=f"Spread arbitrage: {spread:.1%} spread between Yes/No",
                    timestamp=datetime.now()
                )
                signal.expected_return = self.calculate_expected_return(signal)
                signal.position_size = self.calculate_position_size(signal)
                signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error analyzing market: {e}")
        
        return signals
    
    # Position Management Functions
    
    def open_position(self, signal: TradingSignal) -> Optional[Position]:
        """Open a new position based on signal."""
        # Check if we already have a position in this market
        if signal.market_id in self.positions:
            logger.warning(f"Already have position in market {signal.market_id}")
            return None
        
        # Check correlation with existing positions
        correlation = self.check_correlation(signal)
        if correlation > 0.5:
            logger.warning(f"High correlation ({correlation:.1%}) with existing positions")
            return None
        
        # Create position
        position = Position(
            market_id=signal.market_id,
            market_question=signal.market_question,
            direction=signal.direction,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            position_size=signal.position_size,
            stop_price=signal.stop_price,
            target_price=signal.target_price,
            entry_time=datetime.now(),
            pnl=0.0,
            pnl_percent=0.0
        )
        
        # Add to positions
        self.positions[signal.market_id] = position
        
        # Log trade
        self.trading_history.append({
            "action": "open",
            "position": position.to_dict(),
            "signal": signal.to_dict(),
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Opened position: {signal.market_question} ({signal.direction.value})")
        return position
    
    def update_position(self, market_id: str, current_price: float) -> Optional[Position]:
        """Update position with current price."""
        if market_id not in self.positions:
            return None
        
        position = self.positions[market_id]
        position.current_price = current_price
        
        # Calculate P&L
        if position.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            position.pnl = (current_price - position.entry_price) * position.position_size
            position.pnl_percent = (current_price - position.entry_price) / position.entry_price
        else:  # SHORT
            position.pnl = (position.entry_price - current_price) * position.position_size
            position.pnl_percent = (position.entry_price - current_price) / position.entry_price
        
        return position
    
    def close_position(self, market_id: str, exit_price: float, reason: str = "manual") -> Optional[Dict]:
        """Close a position."""
        if market_id not in self.positions:
            return None
        
        position = self.positions[market_id]
        
        # Calculate final P&L
        if position.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            pnl = (exit_price - position.entry_price) * position.position_size
            pnl_percent = (exit_price - position.entry_price) / position.entry_price
        else:  # SHORT
            pnl = (position.entry_price - exit_price) * position.position_size
            pnl_percent = (position.entry_price - exit_price) / position.entry_price
        
        # Update capital
        self.capital += pnl
        
        # Create trade record
        trade_record = {
            "action": "close",
            "market_id": market_id,
            "market_question": position.market_question,
            "direction": position.direction.value,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "position_size": position.position_size,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "entry_time": position.entry_time.isoformat(),
            "exit_time": datetime.now().isoformat(),
            "holding_period": (datetime.now() - position.entry_time).total_seconds() / 3600,  # hours
            "reason": reason
        }
        
        # Add to history
        self.trading_history.append(trade_record)
        
        # Remove from positions
        del self.positions[market_id]
        
        logger.info(f"Closed position: {position.market_question} (P&L: {pnl_percent:.1%})")
        return trade_record
    
    def check_stop_losses(self) -> List[Dict]:
        """Check all positions for stop loss triggers."""
        triggered = []
        
        for market_id, position in list(self.positions.items()):
            if self._stop_loss_triggered(position):
                triggered.append({
                    "market_id": market_id,
                    "position": position.to_dict(),
                    "current_price": position.current_price,
                    "stop_price": position.stop_price,
                    "reason": "stop_loss_triggered"
                })
        
        return triggered
    
    def _stop_loss_triggered(self, position: Position) -> bool:
        """Check if stop loss is triggered."""
        if position.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            return position.current_price <= position.stop_price
        else:  # SHORT
            return position.current_price >= position.stop_price
    
    def check_take_profits(self) -> List[Dict]:
        """Check all positions for take profit triggers."""
        triggered = []
        
        for market_id, position in list(self.positions.items()):
            if self._take_profit_triggered(position):
                triggered.append({
                    "market_id": market_id,
                    "position": position.to_dict(),
                    "current_price": position.current_price,
                    "target_price": position.target_price,
                    "reason": "take_profit_triggered"
                })
        
        return triggered
    
    def _take_profit_triggered(self, position: Position) -> bool:
        """Check if take profit is triggered."""
        if position.direction in [TradeDirection.LONG_YES, TradeDirection.LONG_NO]:
            return position.current_price >= position.target_price
        else:  # SHORT
            return position.current_price <= position.target_price
    
    # Performance Analytics
    
    def calculate_performance_metrics(self) -> Dict:
        """Calculate trading performance metrics."""
        if not self.trading_history:
            return {}
        
        # Filter closed trades
        closed_trades = [t for t in self.trading_history if t.get("action") == "close"]
        
        if not closed_trades:
            return {}
        
        # Calculate metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in closed_trades if t.get("pnl", 0) <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        total_pnl_percent = sum(t.get("pnl_percent", 0) for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t.get("pnl", 0) for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t.get("pnl", 0)) for t in losing_trades]) if losing_trades else 0
        
        profit_factor = sum(t.get("pnl", 0) for t in winning_trades) / sum(abs(t.get("pnl", 0)) for t in losing_trades) if losing_trades else float('inf')
        
        avg_holding_period = np.mean([t.get("holding_period", 0) for t in closed_trades]) if closed_trades else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = [t.get("pnl_percent", 0) for t in closed_trades]
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "avg_holding_period_hours": avg_holding_period,
            "sharpe_ratio": sharpe,
            "current_capital": self.capital,
            "open_positions": len(self.positions)
        }
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary."""
        total_exposure = sum(p.position_size * p.current_price for p in self.positions.values())
        total_pnl = sum(p.pnl for p in self.positions.values())
        
        return {
            "capital": self.capital,
            "total_exposure": total_exposure,
            "exposure_percent": total_exposure / self.capital if self.capital > 0 else 0,
            "total_pnl": total_pnl,
            "open_positions": len(self.positions),
            "positions": [p.to_dict() for p in self.positions.values()]
        }

async def main():
    """Test the trading utilities."""
    utils = TradingUtils(capital=1000.0)
    
    # Create a test signal
    test_signal = TradingSignal(
        market_id="test-market-123",
        market_question="Will Bitcoin hit $100,000 in 2026?",
        direction=TradeDirection.LONG_YES,
        confidence=0.7,
        risk_level=RiskLevel.MEDIUM,
        entry_price=0.3,
        target_price=0.5,
        stop_price=0.2,
        position_size=0.0,
        expected_return=0.0,
        reasoning="Test signal for Bitcoin prediction",
        timestamp=datetime.now()
    )
    
    # Calculate position size
    test_signal.position_size = utils.calculate_position_size(test_signal)
    test_signal.expected_return = utils.calculate_expected_return(test_signal)
    
    print("Test Signal:")
    print(f"  Market: {test_signal.market_question}")
    print(f"  Direction: {test_signal.direction.value}")
    print(f"  Position Size: ${test_signal.position_size:.2f}")
    print(f"  Expected Return: {test_signal.expected_return:.1%}")
    print(f"  Risk Level: {test_signal.risk_level.value}")
    
    # Open position
    position = utils.open_position(test_signal)
    if position:
        print(f"\nPosition opened:")
        print(f"  Entry Price: {position.entry_price:.1%}")
        print(f"  Stop Loss: {position.stop_price:.1%}")
        print(f"  Take Profit: {position.target_price:.1%}")
        
        # Update position with current price
        utils.update_position("test-market-123", 0.35)
        print(f"\nPosition updated:")
        print(f"  Current Price: {position.current_price:.1%}")
        print(f"  P&L: {position.pnl_percent:.1%}")
        
        # Close position
        trade = utils.close_position("test-market-123", 0.45, "take_profit")
        if trade:
            print(f"\nPosition closed:")
            print(f"  Exit Price: {trade['exit_price']:.1%}")
            print(f"  P&L: {trade['pnl_percent']:.1%}")
            print(f"  Reason: {trade['reason']}")
    
    # Print performance metrics
    metrics = utils.calculate_performance_metrics()
    print(f"\nPerformance Metrics:")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")

if __name__ == "__main__":
    asyncio.run(main())