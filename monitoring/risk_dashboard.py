#!/usr/bin/env python3
"""
Risk Management Dashboard
Monitors portfolio risk, position limits, and provides real-time alerts.
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
import numpy as np
from dataclasses import dataclass
from enum import Enum
import statistics

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Position:
    """Position data structure."""
    market_id: str
    market_question: str
    direction: str
    entry_price: float
    current_price: float
    position_size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    pnl: float
    pnl_percent: float
    risk_score: float
    
    def to_dict(self) -> Dict:
        return {
            "market_id": self.market_id,
            "market_question": self.market_question,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "position_size": self.position_size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "entry_time": self.entry_time.isoformat(),
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "risk_score": self.risk_score
        }

class RiskDashboard:
    """Comprehensive risk management dashboard."""
    
    def __init__(self, capital: float = 1000.0):
        self.capital = capital
        self.positions: Dict[str, Position] = {}
        self.risk_limits = self._initialize_risk_limits()
        self.alert_history: List[Dict] = []
        
    def _initialize_risk_limits(self) -> Dict:
        """Initialize risk management limits."""
        return {
            "max_position_size_percent": 0.02,  # 2% of capital per position
            "max_total_exposure_percent": 0.20,  # 20% total exposure
            "max_correlation": 0.5,  # Maximum correlation between positions
            "max_drawdown_percent": 0.15,  # 15% maximum drawdown
            "max_daily_loss_percent": 0.05,  # 5% maximum daily loss
            "stop_loss_percent": 0.10,  # 10% stop loss
            "take_profit_percent": 0.25,  # 25% take profit
            "min_liquidity": 1000,  # Minimum $1000 volume
            "max_spread_percent": 0.10,  # Maximum 10% spread
            "max_positions": 20,  # Maximum number of positions
            "max_sector_exposure_percent": 0.30,  # 30% max exposure to one sector
        }
    
    def calculate_position_risk(self, position: Position) -> Dict:
        """Calculate risk metrics for a position."""
        # Calculate distance to stop loss and take profit
        if position.direction in ["long_yes", "long_no"]:
            distance_to_stop = abs(position.current_price - position.stop_loss) / position.current_price
            distance_to_target = abs(position.take_profit - position.current_price) / position.current_price
            risk_reward_ratio = distance_to_target / distance_to_stop if distance_to_stop > 0 else 0
        else:  # SHORT
            distance_to_stop = abs(position.stop_loss - position.current_price) / position.current_price
            distance_to_target = abs(position.current_price - position.take_profit) / position.current_price
            risk_reward_ratio = distance_to_target / distance_to_stop if distance_to_stop > 0 else 0
        
        # Calculate position risk score
        risk_score = 0
        
        # Factor 1: Size relative to capital
        position_value = position.position_size * position.current_price
        size_percent = position_value / self.capital
        if size_percent > self.risk_limits["max_position_size_percent"]:
            risk_score += 30
        elif size_percent > self.risk_limits["max_position_size_percent"] * 0.5:
            risk_score += 15
        
        # Factor 2: Distance to stop loss
        if distance_to_stop < 0.05:  # Within 5% of stop loss
            risk_score += 25
        elif distance_to_stop < 0.10:  # Within 10% of stop loss
            risk_score += 15
        
        # Factor 3: Unrealized loss
        if position.pnl_percent < -0.05:  # 5% loss
            risk_score += 20
        elif position.pnl_percent < -0.02:  # 2% loss
            risk_score += 10
        
        # Factor 4: Holding period
        holding_hours = (datetime.now() - position.entry_time).total_seconds() / 3600
        if holding_hours > 168:  # 1 week
            risk_score += 10
        
        # Factor 5: Risk/reward ratio
        if risk_reward_ratio < 1.0:  # Risk > Reward
            risk_score += 15
        
        # Normalize risk score to 0-100
        risk_score = min(100, risk_score)
        
        # Determine risk level
        if risk_score < 20:
            risk_level = RiskLevel.LOW
        elif risk_score < 40:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 60:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        return {
            "position": position.to_dict(),
            "risk_score": risk_score,
            "risk_level": risk_level.value,
            "distance_to_stop": distance_to_stop,
            "distance_to_target": distance_to_target,
            "risk_reward_ratio": risk_reward_ratio,
            "position_value": position_value,
            "size_percent": size_percent,
            "holding_hours": holding_hours
        }
    
    def calculate_portfolio_risk(self) -> Dict:
        """Calculate overall portfolio risk metrics."""
        if not self.positions:
            return {
                "total_positions": 0,
                "total_exposure": 0,
                "exposure_percent": 0,
                "total_pnl": 0,
                "pnl_percent": 0,
                "risk_level": RiskLevel.LOW.value,
                "alerts": []
            }
        
        # Calculate total exposure
        total_exposure = sum(p.position_size * p.current_price for p in self.positions.values())
        exposure_percent = total_exposure / self.capital
        
        # Calculate total P&L
        total_pnl = sum(p.pnl for p in self.positions.values())
        pnl_percent = total_pnl / self.capital
        
        # Calculate position risk scores
        position_risks = []
        for position in self.positions.values():
            risk = self.calculate_position_risk(position)
            position_risks.append(risk)
        
        # Calculate portfolio risk score
        portfolio_risk_score = 0
        
        # Factor 1: Total exposure
        if exposure_percent > self.risk_limits["max_total_exposure_percent"]:
            portfolio_risk_score += 30
        elif exposure_percent > self.risk_limits["max_total_exposure_percent"] * 0.8:
            portfolio_risk_score += 15
        
        # Factor 2: Number of positions
        if len(self.positions) > self.risk_limits["max_positions"]:
            portfolio_risk_score += 20
        
        # Factor 3: Correlation between positions
        correlation_risk = self._calculate_correlation_risk()
        portfolio_risk_score += correlation_risk * 20
        
        # Factor 4: Drawdown
        max_drawdown = self._calculate_max_drawdown()
        if max_drawdown > self.risk_limits["max_drawdown_percent"]:
            portfolio_risk_score += 30
        elif max_drawdown > self.risk_limits["max_drawdown_percent"] * 0.5:
            portfolio_risk_score += 15
        
        # Factor 5: Concentration risk
        concentration_risk = self._calculate_concentration_risk()
        portfolio_risk_score += concentration_risk * 20
        
        # Normalize risk score to 0-100
        portfolio_risk_score = min(100, portfolio_risk_score)
        
        # Determine portfolio risk level
        if portfolio_risk_score < 20:
            portfolio_risk_level = RiskLevel.LOW
        elif portfolio_risk_score < 40:
            portfolio_risk_level = RiskLevel.MEDIUM
        elif portfolio_risk_score < 60:
            portfolio_risk_level = RiskLevel.HIGH
        else:
            portfolio_risk_level = RiskLevel.CRITICAL
        
        # Generate alerts
        alerts = self._generate_risk_alerts(portfolio_risk_score, position_risks)
        
        return {
            "total_positions": len(self.positions),
            "total_exposure": total_exposure,
            "exposure_percent": exposure_percent,
            "total_pnl": total_pnl,
            "pnl_percent": pnl_percent,
            "portfolio_risk_score": portfolio_risk_score,
            "portfolio_risk_level": portfolio_risk_level.value,
            "position_risks": position_risks,
            "alerts": alerts,
            "risk_limits": self.risk_limits,
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_correlation_risk(self) -> float:
        """Calculate correlation risk between positions."""
        if len(self.positions) < 2:
            return 0.0
        
        # Simple correlation based on market similarity
        position_questions = [p.market_question for p in self.positions.values()]
        
        # Calculate keyword overlap
        correlation_scores = []
        for i, q1 in enumerate(position_questions):
            for j, q2 in enumerate(position_questions[i+1:], i+1):
                # Simple keyword matching
                words1 = set(q1.lower().split())
                words2 = set(q2.lower().split())
                
                # Remove common words
                common_words = {"will", "the", "a", "an", "be", "is", "are", "was", "were", "in", "on", "at", "to", "for", "of", "with", "by"}
                words1 = words1 - common_words
                words2 = words2 - common_words
                
                if not words1 or not words2:
                    continue
                
                # Calculate Jaccard similarity
                intersection = len(words1.intersection(words2))
                union = len(words1.union(words2))
                
                if union > 0:
                    correlation = intersection / union
                    correlation_scores.append(correlation)
        
        return max(correlation_scores) if correlation_scores else 0.0
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if not self.positions:
            return 0.0
        
        # Get historical P&L (simplified)
        # In real implementation, this would use historical data
        current_pnl = sum(p.pnl for p in self.positions.values())
        
        # Simulate max drawdown as 50% of worst position
        worst_position = min(self.positions.values(), key=lambda p: p.pnl_percent)
        max_drawdown = abs(worst_position.pnl_percent) * 0.5
        
        return min(1.0, max_drawdown)
    
    def _calculate_concentration_risk(self) -> float:
        """Calculate concentration risk."""
        if not self.positions:
            return 0.0
        
        # Calculate exposure by "sector" (simplified)
        sector_exposure = {}
        
        for position in self.positions.values():
            # Assign sector based on keywords
            sector = self._assign_sector(position.market_question)
            position_value = position.position_size * position.current_price
            
            if sector not in sector_exposure:
                sector_exposure[sector] = 0
            sector_exposure[sector] += position_value
        
        # Find maximum sector exposure
        total_exposure = sum(sector_exposure.values())
        if total_exposure == 0:
            return 0.0
        
        max_sector_exposure = max(sector_exposure.values())
        max_sector_percent = max_sector_exposure / total_exposure
        
        return max_sector_percent
    
    def _assign_sector(self, market_question: str) -> str:
        """Assign a sector to a market based on keywords."""
        question_lower = market_question.lower()
        
        sectors = {
            "politics": ["election", "president", "congress", "senate", "political", "vote", "democrat", "republican"],
            "economics": ["interest rate", "inflation", "gdp", "unemployment", "fed", "economy", "economic"],
            "technology": ["ai", "artificial intelligence", "tech", "cryptocurrency", "bitcoin", "ethereum", "blockchain"],
            "geopolitics": ["war", "peace", "sanctions", "tariff", "trade", "geopolitical", "conflict"],
            "sports": ["sports", "championship", "world cup", "super bowl", "olympics", "tournament"],
            "entertainment": ["movie", "music", "award", "oscar", "grammy", "celebrity"],
            "science": ["space", "mars", "moon", "vaccine", "drug", "fda", "clinical trial"],
            "weather": ["hurricane", "earthquake", "weather", "climate", "temperature"]
        }
        
        for sector, keywords in sectors.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return sector
        
        return "other"
    
    def _generate_risk_alerts(self, portfolio_risk_score: float, position_risks: List[Dict]) -> List[Dict]:
        """Generate risk alerts based on current risk levels."""
        alerts = []
        
        # Portfolio-level alerts
        if portfolio_risk_score > 60:
            alerts.append({
                "level": "critical",
                "type": "portfolio_risk",
                "message": f"Portfolio risk score is critical: {portfolio_risk_score:.0f}/100",
                "action": "Reduce overall exposure immediately",
                "timestamp": datetime.now().isoformat()
            })
        elif portfolio_risk_score > 40:
            alerts.append({
                "level": "high",
                "type": "portfolio_risk",
                "message": f"Portfolio risk score is high: {portfolio_risk_score:.0f}/100",
                "action": "Review positions and consider reducing exposure",
                "timestamp": datetime.now().isoformat()
            })
        
        # Position-level alerts
        for risk in position_risks:
            position = risk["position"]
            
            if risk["risk_level"] == "critical":
                alerts.append({
                    "level": "critical",
                    "type": "position_risk",
                    "message": f"Critical risk in {position['market_question'][:50]}...",
                    "action": f"Consider closing position (Risk score: {risk['risk_score']:.0f})",
                    "market_id": position["market_id"],
                    "risk_score": risk["risk_score"],
                    "timestamp": datetime.now().isoformat()
                })
            elif risk["risk_level"] == "high":
                alerts.append({
                    "level": "high",
                    "type": "position_risk",
                    "message": f"High risk in {position['market_question'][:50]}...",
                    "action": f"Monitor closely and consider tightening stop loss",
                    "market_id": position["market_id"],
                    "risk_score": risk["risk_score"],
                    "timestamp": datetime.now().isoformat()
                })
            
            # Check stop loss proximity
            if risk["distance_to_stop"] < 0.02:  # Within 2% of stop loss
                alerts.append({
                    "level": "high",
                    "type": "stop_loss_proximity",
                    "message": f"Position approaching stop loss: {position['market_question'][:50]}...",
                    "action": "Prepare for potential stop loss trigger",
                    "market_id": position["market_id"],
                    "distance_to_stop": risk["distance_to_stop"],
                    "timestamp": datetime.now().isoformat()
                })
        
        # Exposure alerts
        total_exposure = sum(p.position_size * p.current_price for p in self.positions.values())
        exposure_percent = total_exposure / self.capital
        
        if exposure_percent > self.risk_limits["max_total_exposure_percent"]:
            alerts.append({
                "level": "high",
                "type": "exposure_limit",
                "message": f"Total exposure ({exposure_percent:.1%}) exceeds limit ({self.risk_limits['max_total_exposure_percent']:.1%})",
                "action": "Reduce position sizes or close some positions",
                "exposure_percent": exposure_percent,
                "limit": self.risk_limits["max_total_exposure_percent"],
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def generate_risk_report(self) -> str:
        """Generate a comprehensive risk report."""
        portfolio_risk = self.calculate_portfolio_risk()
        
        report = []
        report.append("=" * 80)
        report.append("POLYMARKET RISK MANAGEMENT DASHBOARD")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        # Portfolio Summary
        report.append("\n1. PORTFOLIO SUMMARY")
        report.append("-" * 40)
        report.append(f"Total Capital: ${self.capital:,.2f}")
        report.append(f"Total Positions: {portfolio_risk['total_positions']}")
        report.append(f"Total Exposure: ${portfolio_risk['total_exposure']:,.2f} ({portfolio_risk['exposure_percent']:.1%})")
        report.append(f"Total P&L: ${portfolio_risk['total_pnl']:,.2f} ({portfolio_risk['pnl_percent']:.1%})")
        report.append(f"Portfolio Risk Score: {portfolio_risk['portfolio_risk_score']:.0f}/100 ({portfolio_risk['portfolio_risk_level'].upper()})")
        
        # Risk Limits
        report.append("\n2. RISK LIMITS")
        report.append("-" * 40)
        limits = portfolio_risk['risk_limits']
        report.append(f"Max Position Size: {limits['max_position_size_percent']:.1%} of capital")
        report.append(f"Max Total Exposure: {limits['max_total_exposure_percent']:.1%} of capital")
        report.append(f"Max Drawdown: {limits['max_drawdown_percent']:.1%}")
        report.append(f"Max Daily Loss: {limits['max_daily_loss_percent']:.1%}")
        report.append(f"Stop Loss: {limits['stop_loss_percent']:.1%}")
        report.append(f"Take Profit: {limits['take_profit_percent']:.1%}")
        report.append(f"Max Positions: {limits['max_positions']}")
        
        # Position Risk
        if portfolio_risk['position_risks']:
            report.append("\n3. POSITION RISK ANALYSIS")
            report.append("-" * 40)
            
            for risk in portfolio_risk['position_risks']:
                position = risk['position']
                risk_level_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴"
                }[risk['risk_level']]
                
                report.append(f"\n{risk_level_emoji} {position['market_question'][:60]}...")
                report.append(f"   Direction: {position['direction']}")
                report.append(f"   Size: ${position['position_size']:,.2f} ({risk['size_percent']:.1%} of capital)")
                report.append(f"   Entry: {position['entry_price']:.1%} → Current: {position['current_price']:.1%}")
                report.append(f"   Stop: {position['stop_loss']:.1%} → Target: {position['take_profit']:.1%}")
                report.append(f"   P&L: ${position['pnl']:,.2f} ({position['pnl_percent']:.1%})")
                report.append(f"   Risk Score: {risk['risk_score']:.0f}/100 ({risk['risk_level'].upper()})")
                report.append(f"   Risk/Reward: {risk['risk_reward_ratio']:.2f}")
                report.append(f"   Holding: {risk['holding_hours']:.1f} hours")
        
        # Alerts
        if portfolio_risk['alerts']:
            report.append("\n4. RISK ALERTS")
            report.append("-" * 40)
            
            for alert in portfolio_risk['alerts']:
                level_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴"
                }[alert['level']]
                
                report.append(f"\n{level_emoji} {alert['message']}")
                report.append(f"   Action: {alert['action']}")
                report.append(f"   Type: {alert['type']}")
        
        # Recommendations
        report.append("\n5. RECOMMENDATIONS")
        report.append("-" * 40)
        
        recommendations = []
        
        if portfolio_risk['exposure_percent'] > limits['max_total_exposure_percent'] * 0.8:
            recommendations.append("⚠️  Exposure is approaching limit. Consider reducing position sizes.")
        
        if portfolio_risk['portfolio_risk_score'] > 40:
            recommendations.append("⚠️  Portfolio risk is elevated. Review positions and tighten stops.")
        
        if portfolio_risk['total_positions'] > limits['max_positions'] * 0.8:
            recommendations.append("⚠️  Approaching maximum number of positions. Avoid opening new positions.")
        
        # Check for concentration
        sector_exposure = {}
        for position in self.positions.values():
            sector = self._assign_sector(position.market_question)
            position_value = position.position_size * position.current_price
            sector_exposure[sector] = sector_exposure.get(sector, 0) + position_value
        
        total_exposure = sum(sector_exposure.values())
        if total_exposure > 0:
            max_sector = max(sector_exposure.items(), key=lambda x: x[1])
            max_sector_percent = max_sector[1] / total_exposure
            
            if max_sector_percent > limits['max_sector_exposure_percent']:
                recommendations.append(f"⚠️  Concentration risk: {max_sector[0]} sector is {max_sector_percent:.1%} of portfolio.")
        
        if not recommendations:
            recommendations.append("✅ Portfolio risk is within acceptable limits.")
        
        for rec in recommendations:
            report.append(rec)
        
        return "\n".join(report)

def main():
    """Test the risk dashboard."""
    dashboard = RiskDashboard(capital=1000.0)
    
    # Add some test positions
    test_positions = [
        Position(
            market_id="test1",
            market_question="Will Bitcoin hit $100,000 in 2026?",
            direction="long_yes",
            entry_price=0.3,
            current_price=0.35,
            position_size=100.0,
            stop_loss=0.25,
            take_profit=0.5,
            entry_time=datetime.now() - timedelta(hours=24),
            pnl=5.0,
            pnl_percent=0.167,
            risk_score=0.0
        ),
        Position(
            market_id="test2",
            market_question="Will the Fed cut interest rates in March 2026?",
            direction="short_yes",
            entry_price=0.8,
            current_price=0.75,
            position_size=150.0,
            stop_loss=0.85,
            take_profit=0.65,
            entry_time=datetime.now() - timedelta(hours=48),
            pnl=7.5,
            pnl_percent=0.0625,
            risk_score=0.0
        )
    ]
    
    for position in test_positions:
        dashboard.positions[position.market_id] = position
    
    # Generate risk report
    report = dashboard.generate_risk_report()
    print(report)

if __name__ == "__main__":
    main()