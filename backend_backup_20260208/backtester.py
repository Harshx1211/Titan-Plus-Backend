"""
Titan Plus Backtesting Framework
=================================
Institutional-grade backtesting with realistic simulation.

Features:
- Transaction cost modeling
- Slippage simulation
- Position sizing
- Portfolio metrics (Sharpe, Sortino, Max DD)
- Equity curve tracking
- Trade-by-trade analysis

Author: Titan Plus Team
Version: 1.0.0
Date: 2026-02-08
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import logging
import json

logger = logging.getLogger("backtester")


class TransactionCostModel:
    """Realistic transaction cost modeling for Indian options."""
    
    def __init__(self):
        # Per-order costs
        self.BROKERAGE_PER_ORDER = 20.0  # ₹20 flat
        self.STT_RATE = 0.0005  # 0.05% on sell side
        self.EXCHANGE_FEE_RATE = 0.00002  # 0.002%
        self.SEBI_FEE_RATE = 0.0000001  # Minimal
        self.GST_RATE = 0.18  # 18% on brokerage + fees
        
        # Slippage parameters
        self.BASE_SLIPPAGE_POINTS = 5.0
        self.VIX_SLIPPAGE_MULTIPLIER = {
            (0, 15): 1.0,
            (15, 20): 1.2,
            (20, 25): 1.5,
            (25, 100): 2.0
        }
        
    def calculate_entry_cost(
        self, 
        premium: float, 
        quantity: int, 
        lot_size: int = 75
    ) -> float:
        """Calculate total cost for entry."""
        trade_value = premium * quantity * lot_size
        
        brokerage = self.BROKERAGE_PER_ORDER
        exchange_fee = trade_value * self.EXCHANGE_FEE_RATE
        sebi_fee = trade_value * self.SEBI_FEE_RATE
        
        taxable = brokerage + exchange_fee
        gst = taxable * self.GST_RATE
        
        return brokerage + exchange_fee + sebi_fee + gst
    
    def calculate_exit_cost(
        self, 
        premium: float, 
        quantity: int, 
        lot_size: int = 75
    ) -> float:
        """Calculate total cost for exit (includes STT)."""
        trade_value = premium * quantity * lot_size
        
        brokerage = self.BROKERAGE_PER_ORDER
        stt = trade_value * self.STT_RATE
        exchange_fee = trade_value * self.EXCHANGE_FEE_RATE
        sebi_fee = trade_value * self.SEBI_FEE_RATE
        
        taxable = brokerage + exchange_fee
        gst = taxable * self.GST_RATE
        
        return brokerage + stt + exchange_fee + sebi_fee + gst
    
    def calculate_slippage(
        self, 
        signal_price: float, 
        vix: float = 15.0,
        oi: int = 100000,
        is_entry: bool = True
    ) -> float:
        """
        Calculate realistic slippage.
        
        Returns:
            Actual fill price
        """
        base_slippage = self.BASE_SLIPPAGE_POINTS
        
        # VIX adjustment
        vix_mult = 1.0
        for (low, high), mult in self.VIX_SLIPPAGE_MULTIPLIER.items():
            if low <= vix < high:
                vix_mult = mult
                break
        
        # Liquidity adjustment
        if oi < 50000:
            vix_mult *= 1.5
        elif oi > 500000:
            vix_mult *= 0.8
        
        # Random variation (±20%)
        actual_slippage = base_slippage * vix_mult * np.random.uniform(0.8, 1.2)
        
        # Entry = add slippage, Exit = subtract (for long positions)
        if is_entry:
            return signal_price + actual_slippage
        else:
            return signal_price - actual_slippage


class Trade:
    """Represents a single backtest trade."""
    
    def __init__(self, trade_id: str, timestamp: datetime):
        self.trade_id = trade_id
        self.timestamp = timestamp
        
        # Entry details
        self.signal_entry_price = 0.0
        self.actual_entry_price = 0.0
        self.entry_slippage = 0.0
        self.entry_cost = 0.0
        
        # Exit details
        self.signal_exit_price = 0.0
        self.actual_exit_price = 0.0
        self.exit_slippage = 0.0
        self.exit_cost = 0.0
        
        # Trade parameters
        self.quantity = 0
        self.lot_size = 75
        
        # Performance
        self.gross_pnl = 0.0
        self.net_pnl = 0.0
        self.return_pct = 0.0
        
        # Metadata
        self.signal_confidence = 0.0
        self.regime = ""
        self.outcome = ""  # 'WIN' or 'LOSS'
        self.exit_reason = ""  # 'TARGET', 'SL', 'EOD'


class Backtester:
    """
    Main backtesting engine.
    """
    
    def __init__(
        self, 
        brain_engine,
        initial_capital: float = 100000,
        lot_size: int = 75
    ):
        self.brain = brain_engine
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.lot_size = lot_size
        
        # Cost model
        self.cost_model = TransactionCostModel()
        
        # Results tracking
        self.trades: List[Trade] = []
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_pnl: Dict[str, float] = {}
        
        # Position sizing
        self.max_risk_per_trade = 0.02  # 2% of capital
        self.max_position_size = 0.20  # 20% of capital
        
    def run(
        self,
        data: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Run backtest on historical data.
        
        Args:
            data: DataFrame with columns:
                ['timestamp', 'spot_price', 'future_price', 'oi', 'vix',
                 'adx', 'basis_res', 'pcr', 'oi_res', 'regime',
                 'option_price', 'option_sl', 'option_target']
            start_date: Start date (optional)
            end_date: End date (optional)
        
        Returns:
            Dictionary with performance metrics
        """
        logger.info("Starting backtest...")
        
        # Filter by date if specified
        if start_date:
            data = data[data['timestamp'] >= start_date]
        if end_date:
            data = data[data['timestamp'] <= end_date]
        
        if len(data) == 0:
            logger.error("No data in specified date range")
            return {}
        
        logger.info(f"Backtesting {len(data)} data points")
        
        # Simulate trade by trade
        for idx, row in data.iterrows():
            self._process_signal(row)
        
        # Calculate final metrics
        metrics = self._calculate_metrics()
        
        logger.info("Backtest complete")
        return metrics
    
    def _process_signal(self, row: pd.Series):
        """Process a single signal/bar."""
        
        # Prepare features for brain
        features = {
            'ADX': row.get('adx', 25.0),
            'BASIS_RES': row.get('basis_res', 0.5),
            'PCR': row.get('pcr', 1.0),
            'OI_RES': row.get('oi_res', 0.5),
            'VIX': row.get('vix', 15.0),
            'GEX': row.get('gex', 0.0)
        }
        
        market_data = {
            'spot_price': row.get('spot_price', 0),
            'future_price': row.get('future_price', 0),
            'oi': row.get('oi', 0),
            'vix': row.get('vix', 15.0),
            'gex': row.get('gex', 0.0)
        }
        
        regime = row.get('regime', 'UNCERTAIN')
        
        # Get brain decision
        decision = self.brain.decide(features, market_data, regime)
        
        # Only trade if approved
        if decision['decision'] != 'APPROVE':
            return
        
        # Execute simulated trade
        self._execute_backtest_trade(row, decision)
    
    def _execute_backtest_trade(self, row: pd.Series, decision: Dict):
        """Execute a single backtest trade."""
        
        timestamp = row.get('timestamp', datetime.now())
        trade_id = f"BT_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        trade = Trade(trade_id, timestamp)
        
        # Entry simulation
        signal_price = row.get('option_price', 100.0)
        vix = row.get('vix', 15.0)
        oi = row.get('oi', 100000)
        
        trade.signal_entry_price = signal_price
        trade.actual_entry_price = self.cost_model.calculate_slippage(
            signal_price, vix, oi, is_entry=True
        )
        trade.entry_slippage = trade.actual_entry_price - signal_price
        
        # Position sizing
        trade.quantity = self._calculate_position_size(row, decision)
        trade.lot_size = self.lot_size
        
        # Entry cost
        trade.entry_cost = self.cost_model.calculate_entry_cost(
            trade.actual_entry_price, trade.quantity, self.lot_size
        )
        
        # Simulate outcome (simplified: use SL/Target from row)
        signal_sl = row.get('option_sl', signal_price - 20)
        signal_target = row.get('option_target', signal_price + 30)
        
        # Simulate with probability based on confidence
        confidence = decision.get('confidence', 0.6)
        hit_target = np.random.random() < confidence
        
        if hit_target:
            trade.signal_exit_price = signal_target
            trade.outcome = 'WIN'
            trade.exit_reason = 'TARGET'
        else:
            trade.signal_exit_price = signal_sl
            trade.outcome = 'LOSS'
            trade.exit_reason = 'SL'
        
        # Exit simulation
        trade.actual_exit_price = self.cost_model.calculate_slippage(
            trade.signal_exit_price, vix, oi, is_entry=False
        )
        trade.exit_slippage = trade.signal_exit_price - trade.actual_exit_price
        
        # Exit cost
        trade.exit_cost = self.cost_model.calculate_exit_cost(
            trade.actual_exit_price, trade.quantity, self.lot_size
        )
        
        # Calculate P&L
        entry_value = trade.actual_entry_price * trade.quantity * self.lot_size
        exit_value = trade.actual_exit_price * trade.quantity * self.lot_size
        
        trade.gross_pnl = exit_value - entry_value
        trade.net_pnl = trade.gross_pnl - trade.entry_cost - trade.exit_cost
        trade.return_pct = (trade.net_pnl / entry_value) * 100 if entry_value > 0 else 0
        
        # Update capital
        self.capital += trade.net_pnl
        
        # Store metadata
        trade.signal_confidence = decision.get('confidence', 0.0)
        trade.regime = row.get('regime', 'UNKNOWN')
        
        # Record trade
        self.trades.append(trade)
        self.equity_curve.append((timestamp, self.capital))
        
        # Update daily P&L
        date_key = timestamp.strftime('%Y-%m-%d')
        self.daily_pnl[date_key] = self.daily_pnl.get(date_key, 0) + trade.net_pnl
        
        logger.debug(
            f"Trade {trade_id}: {trade.outcome} "
            f"Entry={trade.actual_entry_price:.1f}, "
            f"Exit={trade.actual_exit_price:.1f}, "
            f"P&L=₹{trade.net_pnl:.2f}"
        )
    
    def _calculate_position_size(self, row: pd.Series, decision: Dict) -> int:
        """
        Calculate position size in lots.
        
        Uses simplified Kelly criterion.
        """
        confidence = decision.get('confidence', 0.6)
        
        signal_price = row.get('option_price', 100.0)
        signal_sl = row.get('option_sl', signal_price - 20)
        signal_target = row.get('option_target', signal_price + 30)
        
        # Risk and reward
        risk_per_lot = abs(signal_price - signal_sl) * self.lot_size
        reward_per_lot = abs(signal_target - signal_price) * self.lot_size
        
        if risk_per_lot == 0:
            return 1
        
        # Risk-reward ratio
        rr_ratio = reward_per_lot / risk_per_lot
        
        # Kelly fraction (fractional for safety)
        win_prob = confidence
        kelly = ((win_prob * rr_ratio) - (1 - win_prob)) / rr_ratio
        fractional_kelly = max(0, kelly * 0.25)  # Use 25% of Kelly
        
        # Max risk per trade
        max_risk = self.capital * self.max_risk_per_trade
        lots = int((max_risk * fractional_kelly) / risk_per_lot)
        
        # Floor and cap
        lots = max(1, min(lots, 5))
        
        return lots
    
    def _calculate_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        
        if not self.trades:
            return {'error': 'No trades executed'}
        
        # Convert trades to DataFrame for analysis
        trades_data = []
        for t in self.trades:
            trades_data.append({
                'timestamp': t.timestamp,
                'net_pnl': t.net_pnl,
                'return_pct': t.return_pct,
                'outcome': t.outcome,
                'confidence': t.signal_confidence,
                'regime': t.regime
            })
        
        df = pd.DataFrame(trades_data)
        
        # Basic metrics
        total_trades = len(df)
        wins = len(df[df['net_pnl'] > 0])
        losses = len(df[df['net_pnl'] <= 0])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        # P&L metrics
        total_pnl = df['net_pnl'].sum()
        avg_win = df[df['net_pnl'] > 0]['net_pnl'].mean() if wins > 0 else 0
        avg_loss = abs(df[df['net_pnl'] <= 0]['net_pnl'].mean()) if losses > 0 else 0
        
        # Profit factor
        gross_profit = df[df['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(df[df['net_pnl'] <= 0]['net_pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Risk metrics
        returns = df['return_pct'] / 100
        
        # Sharpe ratio (annualized)
        if returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0 and downside_returns.std() > 0:
            sortino_ratio = (returns.mean() / downside_returns.std()) * np.sqrt(252)
        else:
            sortino_ratio = 0
        
        # Drawdown analysis
        equity = pd.Series([e[1] for e in self.equity_curve])
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        max_drawdown = drawdown.min() * 100
        
        # Calculate max drawdown duration
        dd_duration = 0
        current_dd = 0
        for dd in drawdown:
            if dd < 0:
                current_dd += 1
                dd_duration = max(dd_duration, current_dd)
            else:
                current_dd = 0
        
        # Calmar ratio
        if abs(max_drawdown) > 0:
            calmar_ratio = ((self.capital - self.initial_capital) / self.initial_capital * 100) / abs(max_drawdown)
        else:
            calmar_ratio = 0
        
        # Compile metrics
        metrics = {
            # Trade statistics
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            
            # P&L
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'largest_win': df['net_pnl'].max(),
            'largest_loss': df['net_pnl'].min(),
            
            # Returns
            'initial_capital': self.initial_capital,
            'final_capital': self.capital,
            'net_return': self.capital - self.initial_capital,
            'return_pct': ((self.capital - self.initial_capital) / self.initial_capital) * 100,
            
            # Risk metrics
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'max_dd_duration': dd_duration,
            'calmar_ratio': calmar_ratio,
            
            # Regime breakdown
            'regime_breakdown': df.groupby('regime')['net_pnl'].agg(['count', 'sum', 'mean']).to_dict()
        }
        
        return metrics
    
    def print_report(self, metrics: Dict):
        """Print formatted backtest report."""
        
        if 'error' in metrics:
            print(f"\nERROR: {metrics['error']}")
            return
        
        print("\n" + "="*70)
        print("BACKTEST RESULTS")
        print("="*70)
        
        print("\n📊 TRADE STATISTICS")
        print(f"  Total Trades:        {metrics['total_trades']}")
        print(f"  Wins:                {metrics['wins']}")
        print(f"  Losses:              {metrics['losses']}")
        print(f"  Win Rate:            {metrics['win_rate']:.2f}%")
        
        print("\n💰 PROFIT & LOSS")
        print(f"  Total P&L:           ₹{metrics['total_pnl']:,.2f}")
        print(f"  Average Win:         ₹{metrics['avg_win']:,.2f}")
        print(f"  Average Loss:        ₹{metrics['avg_loss']:,.2f}")
        print(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
        print(f"  Largest Win:         ₹{metrics['largest_win']:,.2f}")
        print(f"  Largest Loss:        ₹{metrics['largest_loss']:,.2f}")
        
        print("\n📈 RETURNS")
        print(f"  Initial Capital:     ₹{metrics['initial_capital']:,.2f}")
        print(f"  Final Capital:       ₹{metrics['final_capital']:,.2f}")
        print(f"  Net Return:          ₹{metrics['net_return']:,.2f}")
        print(f"  Return %:            {metrics['return_pct']:.2f}%")
        
        print("\n⚠️  RISK METRICS")
        print(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio:       {metrics['sortino_ratio']:.2f}")
        print(f"  Max Drawdown:        {metrics['max_drawdown']:.2f}%")
        print(f"  Max DD Duration:     {metrics['max_dd_duration']} trades")
        print(f"  Calmar Ratio:        {metrics['calmar_ratio']:.2f}")
        
        print("\n" + "="*70)
        
        # Assessment
        print("\n🎯 ASSESSMENT")
        
        if metrics['sharpe_ratio'] > 2.0:
            print("  ✓ Excellent Sharpe Ratio (>2.0)")
        elif metrics['sharpe_ratio'] > 1.5:
            print("  ✓ Good Sharpe Ratio (>1.5)")
        elif metrics['sharpe_ratio'] > 1.0:
            print("  ⚠ Acceptable Sharpe Ratio (>1.0)")
        else:
            print("  ✗ Poor Sharpe Ratio (<1.0)")
        
        if metrics['win_rate'] > 60:
            print("  ✓ Excellent Win Rate (>60%)")
        elif metrics['win_rate'] > 55:
            print("  ✓ Good Win Rate (>55%)")
        else:
            print("  ⚠ Low Win Rate (<55%)")
        
        if metrics['max_drawdown'] > -20:
            print("  ✓ Acceptable Drawdown (<20%)")
        else:
            print("  ✗ High Drawdown (>20%)")
        
        if metrics['profit_factor'] > 2.0:
            print("  ✓ Excellent Profit Factor (>2.0)")
        elif metrics['profit_factor'] > 1.5:
            print("  ✓ Good Profit Factor (>1.5)")
        else:
            print("  ⚠ Low Profit Factor (<1.5)")
        
        print("\n" + "="*70)
    
    def export_trades(self, filename: str = "backtest_trades.csv"):
        """Export trade log to CSV."""
        trades_data = []
        for t in self.trades:
            trades_data.append({
                'trade_id': t.trade_id,
                'timestamp': t.timestamp,
                'outcome': t.outcome,
                'signal_entry': t.signal_entry_price,
                'actual_entry': t.actual_entry_price,
                'signal_exit': t.signal_exit_price,
                'actual_exit': t.actual_exit_price,
                'quantity': t.quantity,
                'gross_pnl': t.gross_pnl,
                'net_pnl': t.net_pnl,
                'return_pct': t.return_pct,
                'entry_cost': t.entry_cost,
                'exit_cost': t.exit_cost,
                'confidence': t.signal_confidence,
                'regime': t.regime,
                'exit_reason': t.exit_reason
            })
        
        df = pd.DataFrame(trades_data)
        df.to_csv(filename, index=False)
        logger.info(f"Trades exported to {filename}")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Mock brain for testing
    class MockBrain:
        def decide(self, features, market_data, regime):
            return {
                'decision': 'APPROVE' if np.random.random() > 0.5 else 'BLOCK',
                'confidence': np.random.uniform(0.6, 0.9),
                'probability': np.random.uniform(0.6, 0.9)
            }
    
    # Create sample data
    dates = pd.date_range('2024-01-01', '2024-12-31', freq='15min')
    dates = dates[(dates.hour >= 9) & (dates.hour < 16)]  # Market hours
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'spot_price': 24500 + np.cumsum(np.random.randn(len(dates)) * 10),
        'future_price': 24505 + np.cumsum(np.random.randn(len(dates)) * 10),
        'oi': np.random.randint(80000, 150000, len(dates)),
        'vix': np.random.uniform(12, 22, len(dates)),
        'adx': np.random.uniform(20, 40, len(dates)),
        'basis_res': np.random.uniform(0.3, 0.8, len(dates)),
        'pcr': np.random.uniform(0.8, 1.2, len(dates)),
        'oi_res': np.random.uniform(0.4, 0.7, len(dates)),
        'regime': np.random.choice(['TRENDING', 'SIDEWAYS_NORMAL'], len(dates)),
        'option_price': np.random.uniform(80, 150, len(dates)),
        'option_sl': np.random.uniform(60, 100, len(dates)),
        'option_target': np.random.uniform(120, 200, len(dates)),
        'gex': np.random.uniform(-500, 500, len(dates))
    })
    
    # Run backtest
    brain = MockBrain()
    backtester = Backtester(brain, initial_capital=100000)
    
    # Sample first 1000 rows for demo
    results = backtester.run(sample_data.head(1000))
    
    # Print report
    backtester.print_report(results)
    
    # Export trades
    backtester.export_trades()
