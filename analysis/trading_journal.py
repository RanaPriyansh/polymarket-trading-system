#!/usr/bin/env python3
"""
Trading Journal and Performance Tracker
Tracks trades, analyzes performance, and provides insights for improvement.
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import sqlite3
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum
import statistics
import matplotlib.pyplot as plt
import io
import base64

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradeStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class TradeOutcome(Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"

@dataclass
class TradeRecord:
    """Complete trade record."""
    trade_id: str
    market_id: str
    market_question: str
    direction: str  # long_yes, long_no, short_yes, short_no
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    stop_loss: float
    take_profit: float
    entry_time: datetime
    exit_time: Optional[datetime]
    status: TradeStatus
    outcome: TradeOutcome
    pnl: float
    pnl_percent: float
    fees: float
    reasoning: str
    tags: List[str]
    lessons_learned: Optional[str]
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['entry_time'] = self.entry_time.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        data['status'] = self.status.value
        data['outcome'] = self.outcome.value
        return data

class TradingJournal:
    """Comprehensive trading journal and performance tracker."""
    
    def __init__(self, db_path: str = "/root/projects/polymarket-trading-system/data/trading_journal.db"):
        self.db_path = db_path
        self.setup_database()
        
    def setup_database(self):
        """Initialize database for trading journal."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                market_id TEXT,
                market_question TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                position_size REAL,
                stop_loss REAL,
                take_profit REAL,
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                status TEXT,
                outcome TEXT,
                pnl REAL,
                pnl_percent REAL,
                fees REAL,
                reasoning TEXT,
                tags TEXT,
                lessons_learned TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                date DATE PRIMARY KEY,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                total_pnl_percent REAL,
                avg_win REAL,
                avg_loss REAL,
                profit_factor REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                avg_holding_period REAL,
                best_trade REAL,
                worst_trade REAL,
                notes TEXT
            )
        ''')
        
        # Strategy performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_performance (
                strategy_name TEXT,
                date DATE,
                trades INTEGER,
                win_rate REAL,
                total_pnl REAL,
                avg_pnl_percent REAL,
                PRIMARY KEY (strategy_name, date)
            )
        ''')
        
        # Market categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_categories (
                market_id TEXT PRIMARY KEY,
                category TEXT,
                subcategory TEXT,
                keywords TEXT,
                added_date TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Trading journal database initialized at {self.db_path}")
    
    def record_trade(self, trade: TradeRecord) -> bool:
        """Record a trade in the journal."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO trades 
                (trade_id, market_id, market_question, direction, entry_price, exit_price,
                 position_size, stop_loss, take_profit, entry_time, exit_time, status,
                 outcome, pnl, pnl_percent, fees, reasoning, tags, lessons_learned)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade.trade_id,
                trade.market_id,
                trade.market_question,
                trade.direction,
                trade.entry_price,
                trade.exit_price,
                trade.position_size,
                trade.stop_loss,
                trade.take_profit,
                trade.entry_time.isoformat(),
                trade.exit_time.isoformat() if trade.exit_time else None,
                trade.status.value,
                trade.outcome.value,
                trade.pnl,
                trade.pnl_percent,
                trade.fees,
                trade.reasoning,
                json.dumps(trade.tags),
                trade.lessons_learned
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Recorded trade: {trade.trade_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
            return False
    
    def get_trade_history(self, days_back: int = 30, limit: int = 100) -> List[Dict]:
        """Get trade history."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM trades 
            WHERE entry_time >= datetime('now', ?)
            ORDER BY entry_time DESC
            LIMIT ?
        ''', (f'-{days_back} days', limit))
        
        columns = [description[0] for description in cursor.description]
        trades = []
        
        for row in cursor.fetchall():
            trade = dict(zip(columns, row))
            # Parse JSON fields
            if trade['tags']:
                trade['tags'] = json.loads(trade['tags'])
            trades.append(trade)
        
        conn.close()
        return trades
    
    def calculate_performance_metrics(self, days_back: int = 30) -> Dict:
        """Calculate comprehensive performance metrics."""
        trades = self.get_trade_history(days_back)
        
        if not trades:
            return {"error": "No trades found"}
        
        # Filter closed trades
        closed_trades = [t for t in trades if t['status'] == 'closed']
        
        if not closed_trades:
            return {"error": "No closed trades found"}
        
        # Basic metrics
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t['pnl'] for t in closed_trades)
        total_pnl_percent = sum(t['pnl_percent'] for t in closed_trades) / total_trades if total_trades > 0 else 0
        
        avg_win = statistics.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = statistics.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0
        
        profit_factor = sum(t['pnl'] for t in winning_trades) / sum(abs(t['pnl']) for t in losing_trades) if losing_trades else float('inf')
        
        # Calculate holding periods
        holding_periods = []
        for trade in closed_trades:
            if trade['exit_time'] and trade['entry_time']:
                entry = datetime.fromisoformat(trade['entry_time'])
                exit = datetime.fromisoformat(trade['exit_time'])
                holding_period = (exit - entry).total_seconds() / 3600  # hours
                holding_periods.append(holding_period)
        
        avg_holding_period = statistics.mean(holding_periods) if holding_periods else 0
        
        # Calculate Sharpe ratio (simplified)
        returns = [t['pnl_percent'] for t in closed_trades]
        if len(returns) > 1:
            sharpe = statistics.mean(returns) / statistics.stdev(returns) if statistics.stdev(returns) > 0 else 0
        else:
            sharpe = 0
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in closed_trades:
            running_total += trade['pnl']
            cumulative_pnl.append(running_total)
        
        max_drawdown = 0
        peak = cumulative_pnl[0] if cumulative_pnl else 0
        
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            drawdown = peak - pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Best and worst trades
        best_trade = max(closed_trades, key=lambda x: x['pnl_percent'])['pnl_percent'] if closed_trades else 0
        worst_trade = min(closed_trades, key=lambda x: x['pnl_percent'])['pnl_percent'] if closed_trades else 0
        
        return {
            "period_days": days_back,
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
            "max_drawdown": max_drawdown,
            "best_trade_percent": best_trade,
            "worst_trade_percent": worst_trade,
            "risk_reward_ratio": avg_win / avg_loss if avg_loss > 0 else float('inf')
        }
    
    def analyze_strategy_performance(self, days_back: int = 30) -> Dict:
        """Analyze performance by strategy."""
        trades = self.get_trade_history(days_back)
        
        # Group trades by strategy (extracted from tags or reasoning)
        strategy_trades = {}
        
        for trade in trades:
            # Extract strategy from tags or reasoning
            strategy = "unknown"
            if trade['tags']:
                for tag in trade['tags']:
                    if tag.startswith('strategy:'):
                        strategy = tag[9:]
                        break
            
            if strategy == "unknown" and trade['reasoning']:
                # Try to extract strategy from reasoning
                reasoning_lower = trade['reasoning'].lower()
                if 'mean reversion' in reasoning_lower:
                    strategy = 'mean_reversion'
                elif 'volume' in reasoning_lower:
                    strategy = 'volume_based'
                elif 'sentiment' in reasoning_lower:
                    strategy = 'sentiment_based'
                elif 'arbitrage' in reasoning_lower:
                    strategy = 'arbitrage'
                elif 'news' in reasoning_lower:
                    strategy = 'news_based'
            
            if strategy not in strategy_trades:
                strategy_trades[strategy] = []
            strategy_trades[strategy].append(trade)
        
        # Calculate metrics for each strategy
        strategy_metrics = {}
        
        for strategy, trades_list in strategy_trades.items():
            if not trades_list:
                continue
            
            closed_trades = [t for t in trades_list if t['status'] == 'closed']
            
            if not closed_trades:
                continue
            
            total_trades = len(closed_trades)
            winning_trades = [t for t in closed_trades if t['pnl'] > 0]
            
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            total_pnl = sum(t['pnl'] for t in closed_trades)
            avg_pnl_percent = sum(t['pnl_percent'] for t in closed_trades) / total_trades if total_trades > 0 else 0
            
            strategy_metrics[strategy] = {
                "total_trades": total_trades,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "avg_pnl_percent": avg_pnl_percent,
                "winning_trades": len(winning_trades),
                "losing_trades": total_trades - len(winning_trades)
            }
        
        return strategy_metrics
    
    def generate_performance_report(self, days_back: int = 30) -> str:
        """Generate a comprehensive performance report."""
        metrics = self.calculate_performance_metrics(days_back)
        strategy_metrics = self.analyze_strategy_performance(days_back)
        recent_trades = self.get_trade_history(days_back, limit=10)
        
        report = []
        report.append("=" * 80)
        report.append("POLYMARKET TRADING PERFORMANCE REPORT")
        report.append(f"Period: Last {days_back} days")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        # Overall Performance
        report.append("\n1. OVERALL PERFORMANCE")
        report.append("-" * 40)
        report.append(f"Total Trades: {metrics['total_trades']}")
        report.append(f"Win Rate: {metrics['win_rate']:.1%}")
        report.append(f"Total P&L: ${metrics['total_pnl']:.2f}")
        report.append(f"Average P&L per Trade: {metrics['total_pnl_percent']:.1%}")
        report.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
        report.append(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        report.append(f"Max Drawdown: ${metrics['max_drawdown']:.2f}")
        report.append(f"Risk/Reward Ratio: {metrics['risk_reward_ratio']:.2f}")
        
        # Win/Loss Analysis
        report.append("\n2. WIN/LOSS ANALYSIS")
        report.append("-" * 40)
        report.append(f"Winning Trades: {metrics['winning_trades']}")
        report.append(f"Losing Trades: {metrics['losing_trades']}")
        report.append(f"Average Win: ${metrics['avg_win']:.2f}")
        report.append(f"Average Loss: ${metrics['avg_loss']:.2f}")
        report.append(f"Best Trade: {metrics['best_trade_percent']:.1%}")
        report.append(f"Worst Trade: {metrics['worst_trade_percent']:.1%}")
        report.append(f"Average Holding Period: {metrics['avg_holding_period_hours']:.1f} hours")
        
        # Strategy Performance
        report.append("\n3. STRATEGY PERFORMANCE")
        report.append("-" * 40)
        for strategy, strategy_data in strategy_metrics.items():
            report.append(f"\n{strategy.upper()}:")
            report.append(f"  Trades: {strategy_data['total_trades']}")
            report.append(f"  Win Rate: {strategy_data['win_rate']:.1%}")
            report.append(f"  Total P&L: ${strategy_data['total_pnl']:.2f}")
            report.append(f"  Avg P&L: {strategy_data['avg_pnl_percent']:.1%}")
        
        # Recent Trades
        report.append("\n4. RECENT TRADES (Last 10)")
        report.append("-" * 40)
        for trade in recent_trades:
            outcome_emoji = "✅" if trade['pnl'] > 0 else "❌" if trade['pnl'] < 0 else "➖"
            report.append(f"{outcome_emoji} {trade['market_question'][:50]}...")
            report.append(f"   Direction: {trade['direction']}")
            report.append(f"   P&L: {trade['pnl_percent']:.1%} (${trade['pnl']:.2f})")
            report.append(f"   Entry: {trade['entry_price']:.1%} → Exit: {trade['exit_price']:.1%}" if trade['exit_price'] else f"   Entry: {trade['entry_price']:.1%} (Open)")
            report.append("")
        
        # Insights and Recommendations
        report.append("\n5. INSIGHTS AND RECOMMENDATIONS")
        report.append("-" * 40)
        
        insights = []
        
        if metrics['win_rate'] < 0.4:
            insights.append("⚠️  Win rate is below 40%. Consider tightening entry criteria.")
        elif metrics['win_rate'] > 0.6:
            insights.append("✅ Good win rate. Focus on position sizing and risk management.")
        
        if metrics['profit_factor'] < 1.0:
            insights.append("⚠️  Profit factor below 1.0. Losing more than winning on average.")
        elif metrics['profit_factor'] > 2.0:
            insights.append("✅ Excellent profit factor. Strategy is working well.")
        
        if metrics['max_drawdown'] > metrics['total_pnl'] * 0.5:
            insights.append("⚠️  High drawdown relative to profits. Consider reducing position sizes.")
        
        # Find best and worst strategies
        if strategy_metrics:
            best_strategy = max(strategy_metrics.items(), key=lambda x: x[1]['total_pnl'])
            worst_strategy = min(strategy_metrics.items(), key=lambda x: x[1]['total_pnl'])
            
            insights.append(f"📈 Best performing strategy: {best_strategy[0]} (${best_strategy[1]['total_pnl']:.2f})")
            insights.append(f"📉 Worst performing strategy: {worst_strategy[0]} (${worst_strategy[1]['total_pnl']:.2f})")
        
        for insight in insights:
            report.append(insight)
        
        return "\n".join(report)
    
    def create_performance_chart(self, days_back: int = 30) -> str:
        """Create a performance chart and return as base64 image."""
        try:
            trades = self.get_trade_history(days_back)
            closed_trades = [t for t in trades if t['status'] == 'closed']
            
            if not closed_trades:
                return ""
            
            # Sort by entry time
            closed_trades.sort(key=lambda x: x['entry_time'])
            
            # Calculate cumulative P&L
            cumulative_pnl = []
            running_total = 0
            dates = []
            
            for trade in closed_trades:
                running_total += trade['pnl']
                cumulative_pnl.append(running_total)
                dates.append(datetime.fromisoformat(trade['entry_time']))
            
            # Create chart
            plt.figure(figsize=(12, 6))
            plt.plot(dates, cumulative_pnl, marker='o', linestyle='-', linewidth=2, markersize=4)
            plt.axhline(y=0, color='r', linestyle='--', alpha=0.5)
            plt.title(f'Polymarket Trading Performance - Last {days_back} Days', fontsize=16)
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Cumulative P&L ($)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save to base64
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Error creating performance chart: {e}")
            return ""
    
    def export_journal(self, format: str = "json", days_back: int = 30) -> str:
        """Export trading journal in specified format."""
        trades = self.get_trade_history(days_back)
        metrics = self.calculate_performance_metrics(days_back)
        
        if format == "json":
            export_data = {
                "export_date": datetime.now().isoformat(),
                "period_days": days_back,
                "trades": trades,
                "metrics": metrics
            }
            return json.dumps(export_data, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "Trade ID", "Market", "Direction", "Entry Price", "Exit Price",
                "Position Size", "P&L", "P&L %", "Entry Time", "Exit Time",
                "Status", "Outcome", "Reasoning"
            ])
            
            # Write trades
            for trade in trades:
                writer.writerow([
                    trade['trade_id'],
                    trade['market_question'],
                    trade['direction'],
                    trade['entry_price'],
                    trade['exit_price'],
                    trade['position_size'],
                    trade['pnl'],
                    trade['pnl_percent'],
                    trade['entry_time'],
                    trade['exit_time'],
                    trade['status'],
                    trade['outcome'],
                    trade['reasoning']
                ])
            
            return output.getvalue()
        
        else:
            return f"Unsupported format: {format}"

def main():
    """Test the trading journal."""
    journal = TradingJournal()
    
    # Create some test trades
    test_trades = []
    
    for i in range(5):
        trade = TradeRecord(
            trade_id=f"trade_{i+1}",
            market_id=f"market_{i+1}",
            market_question=f"Will event {i+1} happen?",
            direction="long_yes",
            entry_price=0.3 + (i * 0.05),
            exit_price=0.4 + (i * 0.05),
            position_size=100.0,
            stop_loss=0.25,
            take_profit=0.5,
            entry_time=datetime.now() - timedelta(days=30-i*5),
            exit_time=datetime.now() - timedelta(days=30-i*5-2),
            status=TradeStatus.CLOSED,
            outcome=TradeOutcome.WIN if i % 2 == 0 else TradeOutcome.LOSS,
            pnl=10.0 if i % 2 == 0 else -5.0,
            pnl_percent=0.1 if i % 2 == 0 else -0.05,
            fees=0.5,
            reasoning=f"Test trade {i+1}",
            tags=["test", f"strategy:{'mean_reversion' if i % 2 == 0 else 'volume'}"],
            lessons_learned=f"Lesson from trade {i+1}"
        )
        test_trades.append(trade)
        journal.record_trade(trade)
    
    # Generate performance report
    report = journal.generate_performance_report(days_back=30)
    print(report)
    
    # Export journal
    print("\n\nExporting journal to JSON...")
    json_export = journal.export_journal("json", days_back=30)
    with open("/root/projects/polymarket-trading-system/data/journal_export.json", "w") as f:
        f.write(json_export)
    print(f"Exported to journal_export.json")

if __name__ == "__main__":
    main()