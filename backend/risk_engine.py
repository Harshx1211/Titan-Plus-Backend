import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class RiskParameters:
    """Risk management parameters for a trade"""
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    position_size: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float

class InstitutionalRiskEngine:
    """
    Professional-grade risk management system
    Implements institutional position sizing and dynamic target calculation
    """
    
    def __init__(self, account_size: float = 10000):
        self.account_size = account_size
        self.risk_per_trade_pct = 0.01  # 1% risk per trade
        self.max_risk_per_trade = account_size * self.risk_per_trade_pct
        self.usd_to_inr = 83.0  # INR conversion rate
        
        # Multi-target system (institutional approach)
        self.tp1_rr = 1.5  # First target at 1.5R
        self.tp2_rr = 2.5  # Second target at 2.5R
        self.tp3_rr = 4.0  # Third target at 4R (runner)
        
        # Position sizing
        self.tp1_size = 0.50  # 50% at TP1
        self.tp2_size = 0.30  # 30% at TP2
        self.tp3_size = 0.20  # 20% at TP3 (runner)
        
        # Safety limits
        self.max_stop_distance_pct = 0.04  # Maximum 4% stop loss distance
        self.min_stop_distance_pct = 0.005  # Minimum 0.5% stop loss distance
        
        # Active position tracking
        self.active_position: Optional[Dict] = None
        self.position_history: list = []
        
    def calculate_position_parameters(self, 
                                     symbol: str,
                                     side: PositionSide,
                                     entry_price: float,
                                     market_data: pd.DataFrame,
                                     smc_analysis: Dict) -> RiskParameters:
        """
        Calculates comprehensive risk parameters using ATR and SMC levels
        """
        # Calculate ATR for dynamic stop placement
        atr = self._calculate_atr(market_data)
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else entry_price * 0.02
        
        # Determine stop loss based on SMC structure
        stop_loss = self._calculate_smart_stop(
            entry_price, side, current_atr, smc_analysis
        )
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        # Position sizing based on fixed risk
        position_size = self.max_risk_per_trade / risk_per_share if risk_per_share > 0 else 0
        
        # Calculate take profit levels
        if side == PositionSide.LONG:
            tp1 = entry_price + (risk_per_share * self.tp1_rr)
            tp2 = entry_price + (risk_per_share * self.tp2_rr)
            tp3 = entry_price + (risk_per_share * self.tp3_rr)
        else:  # SHORT
            tp1 = entry_price - (risk_per_share * self.tp1_rr)
            tp2 = entry_price - (risk_per_share * self.tp2_rr)
            tp3 = entry_price - (risk_per_share * self.tp3_rr)
        
        # Adjust targets to align with SMC levels (liquidity zones, FVGs)
        tp1, tp2, tp3 = self._align_targets_with_structure(
            [tp1, tp2, tp3], side, smc_analysis
        )
        
        risk_amount = position_size * risk_per_share
        reward_amount = (position_size * self.tp1_size * abs(tp1 - entry_price) +
                        position_size * self.tp2_size * abs(tp2 - entry_price) +
                        position_size * self.tp3_size * abs(tp3 - entry_price))
        
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
        
        return RiskParameters(
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            take_profit_1=round(tp1, 2),
            take_profit_2=round(tp2, 2),
            take_profit_3=round(tp3, 2),
            position_size=round(position_size, 4),
            risk_amount=round(risk_amount, 2),
            reward_amount=round(reward_amount, 2),
            risk_reward_ratio=round(rr_ratio, 2)
        )
    
    def _calculate_smart_stop(self, entry: float, side: PositionSide, 
                             atr: float, smc_analysis: Dict) -> float:
        """
        Calculates stop loss using SMC structure (order blocks, swing points)
        Falls back to ATR-based stop if no structure is available
        
        🔧 FIXED: Added maximum stop distance cap to prevent excessive stops
        """
        # Calculate maximum allowed stop distance (safety limit)
        max_stop_distance = entry * self.max_stop_distance_pct
        min_stop_distance = entry * self.min_stop_distance_pct
        
        # Try to use order block as stop reference
        order_blocks = smc_analysis.get('order_blocks', [])
        
        if side == PositionSide.LONG:
            # For longs, look for bullish OB below entry
            relevant_obs = [ob for ob in order_blocks 
                          if ob.type == "BULLISH_OB" and ob.price_bottom < entry]
            if relevant_obs:
                # Place stop below the strongest OB
                strongest_ob = max(relevant_obs, key=lambda x: x.strength)
                proposed_stop = strongest_ob.price_bottom - (atr * 0.2)  # Small buffer
                
                # Ensure stop is within acceptable range
                stop_distance = entry - proposed_stop
                if stop_distance > max_stop_distance:
                    # Stop too wide, use max distance
                    return entry - max_stop_distance
                elif stop_distance < min_stop_distance:
                    # Stop too tight, use min distance
                    return entry - min_stop_distance
                else:
                    return proposed_stop
            else:
                # Fallback: ATR-based stop with safety cap
                atr_stop = entry - (atr * 1.5)
                stop_distance = entry - atr_stop
                
                if stop_distance > max_stop_distance:
                    # 🔧 FIXED: Cap at maximum allowed distance
                    return entry - max_stop_distance
                elif stop_distance < min_stop_distance:
                    return entry - min_stop_distance
                else:
                    return atr_stop
        
        else:  # SHORT
            # For shorts, look for bearish OB above entry
            relevant_obs = [ob for ob in order_blocks 
                          if ob.type == "BEARISH_OB" and ob.price_top > entry]
            if relevant_obs:
                strongest_ob = max(relevant_obs, key=lambda x: x.strength)
                proposed_stop = strongest_ob.price_top + (atr * 0.2)
                
                # Ensure stop is within acceptable range
                stop_distance = proposed_stop - entry
                if stop_distance > max_stop_distance:
                    return entry + max_stop_distance
                elif stop_distance < min_stop_distance:
                    return entry + min_stop_distance
                else:
                    return proposed_stop
            else:
                # Fallback: ATR-based stop with safety cap
                atr_stop = entry + (atr * 1.5)
                stop_distance = atr_stop - entry
                
                if stop_distance > max_stop_distance:
                    # 🔧 FIXED: Cap at maximum allowed distance
                    return entry + max_stop_distance
                elif stop_distance < min_stop_distance:
                    return entry + min_stop_distance
                else:
                    return atr_stop
    
    def _align_targets_with_structure(self, targets: list, side: PositionSide, 
                                     smc_analysis: Dict) -> Tuple[float, float, float]:
        """
        Adjusts take profit targets to align with SMC structure
        Targets liquidity zones and FVG boundaries
        """
        liquidity_zones = smc_analysis.get('liquidity_zones', [])
        fvgs = smc_analysis.get('fair_value_gaps', [])
        
        adjusted_targets = targets.copy()
        
        # For each target, try to align with nearby structure
        for i, target in enumerate(targets):
            # Check liquidity zones
            for lz in liquidity_zones:
                if side == PositionSide.LONG:
                    # For longs, target liquidity above
                    if lz.type == "EQUAL_HIGHS" and abs(lz.price - target) / target < 0.01:
                        adjusted_targets[i] = lz.price
                        break
                else:
                    # For shorts, target liquidity below
                    if lz.type == "EQUAL_LOWS" and abs(lz.price - target) / target < 0.01:
                        adjusted_targets[i] = lz.price
                        break
            
            # Check FVG boundaries
            for fvg in fvgs:
                if side == PositionSide.LONG:
                    if fvg['type'] == 'BEARISH_FVG' and abs(fvg['bottom'] - target) / target < 0.01:
                        adjusted_targets[i] = fvg['bottom']
                        break
                else:
                    if fvg['type'] == 'BULLISH_FVG' and abs(fvg['top'] - target) / target < 0.01:
                        adjusted_targets[i] = fvg['top']
                        break
        
        return tuple(adjusted_targets)
    
    def validate_new_position(self) -> Tuple[bool, str]:
        """
        Validates if a new position can be opened
        Enforces the 'One Live Position' rule
        """
        if self.active_position is not None:
            return False, "BLOCKED: Active position already exists. Close current position first."
        
        return True, "APPROVED: No active position. Safe to enter."
    
    def open_position(self, symbol: str, side: PositionSide, 
                     risk_params: RiskParameters, metadata: Dict) -> str:
        """
        Opens a new position with full risk parameters
        Returns position ID
        """
        can_enter, message = self.validate_new_position()
        if not can_enter:
            raise ValueError(message)
        
        position_id = f"{symbol}_{side.value}_{int(pd.Timestamp.now().timestamp())}"
        
        self.active_position = {
            'id': position_id,
            'symbol': symbol,
            'side': side.value,
            'entry_price': risk_params.entry_price,
            'stop_loss': risk_params.stop_loss,
            'targets': {
                'tp1': {'price': risk_params.take_profit_1, 'size': self.tp1_size, 'hit': False},
                'tp2': {'price': risk_params.take_profit_2, 'size': self.tp2_size, 'hit': False},
                'tp3': {'price': risk_params.take_profit_3, 'size': self.tp3_size, 'hit': False}
            },
            'position_size': risk_params.position_size,
            'risk_amount': risk_params.risk_amount,
            'expected_reward': risk_params.reward_amount,
            'rr_ratio': risk_params.risk_reward_ratio,
            'metadata': metadata,
            'opened_at': pd.Timestamp.now().isoformat(),
            'status': 'OPEN'
        }
        
        # Calculate stop distance percentage
        stop_distance_pct = abs(risk_params.entry_price - risk_params.stop_loss) / risk_params.entry_price * 100
        
        print(f"🎯 RISK ENGINE: Position opened - {symbol} {side.value}")
        print(f"   Entry: ₹{risk_params.entry_price * self.usd_to_inr:,.2f} | SL: ₹{risk_params.stop_loss * self.usd_to_inr:,.2f} ({stop_distance_pct:.2f}%)")
        print(f"   Targets: ₹{risk_params.take_profit_1 * self.usd_to_inr:,.2f} / ₹{risk_params.take_profit_2 * self.usd_to_inr:,.2f} / ₹{risk_params.take_profit_3 * self.usd_to_inr:,.2f}")
        print(f"   R:R = 1:{risk_params.risk_reward_ratio}")
        
        return position_id
    
    def check_position_status(self, current_price: float) -> Dict:
        """
        Checks current position against price and returns status
        """
        if not self.active_position:
            return {'status': 'NO_POSITION'}
        
        pos = self.active_position
        side = pos['side']
        
        # Check stop loss
        if (side == 'LONG' and current_price <= pos['stop_loss']) or \
           (side == 'SHORT' and current_price >= pos['stop_loss']):
            return {'status': 'STOP_HIT', 'action': 'CLOSE_ALL', 'reason': 'Stop Loss'}
        
        # Check take profits
        actions = []
        for tp_name, tp_data in pos['targets'].items():
            if not tp_data['hit']:
                if (side == 'LONG' and current_price >= tp_data['price']) or \
                   (side == 'SHORT' and current_price <= tp_data['price']):
                    tp_data['hit'] = True
                    actions.append({
                        'target': tp_name,
                        'price': tp_data['price'],
                        'size': tp_data['size']
                    })
        
        if actions:
            return {'status': 'TARGET_HIT', 'actions': actions}
        
        return {'status': 'ACTIVE', 'unrealized_pnl': self._calculate_unrealized_pnl(current_price)}
    
    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculates current unrealized P&L"""
        if not self.active_position:
            return 0.0
        
        pos = self.active_position
        entry = pos['entry_price']
        size = pos['position_size']
        
        if pos['side'] == 'LONG':
            pnl = (current_price - entry) * size
        else:
            pnl = (entry - current_price) * size
        
        return round(pnl, 2)
    
    def close_position(self, exit_price: float, reason: str) -> Dict:
        """
        Closes the active position and returns summary
        """
        if not self.active_position:
            return {'error': 'No active position to close'}
        
        pos = self.active_position
        realized_pnl = self._calculate_unrealized_pnl(exit_price)
        
        summary = {
            'position_id': pos['id'],
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'realized_pnl': realized_pnl,
            'risk_amount': pos['risk_amount'],
            'r_multiple': realized_pnl / pos['risk_amount'] if pos['risk_amount'] > 0 else 0,
            'duration': (pd.Timestamp.now() - pd.Timestamp(pos['opened_at'])).total_seconds() / 3600,
            'close_reason': reason,
            'closed_at': pd.Timestamp.now().isoformat()
        }
        
        self.position_history.append(summary)
        self.active_position = None
        
        print(f"📊 RISK ENGINE: Position closed - {summary['symbol']}")
        print(f"   P&L: ₹{realized_pnl * self.usd_to_inr:,.2f} ({summary['r_multiple']:.2f}R)")
        print(f"   Reason: {reason}")
        
        return summary
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr
    
    def get_performance_metrics(self) -> Dict:
        """Returns comprehensive performance statistics"""
        if not self.position_history:
            return {'status': 'No closed positions yet'}
        
        total_trades = len(self.position_history)
        winning_trades = [t for t in self.position_history if t['realized_pnl'] > 0]
        losing_trades = [t for t in self.position_history if t['realized_pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t['realized_pnl'] for t in self.position_history)
        avg_win = np.mean([t['realized_pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['realized_pnl'] for t in losing_trades]) if losing_trades else 0
        
        profit_factor = abs(sum(t['realized_pnl'] for t in winning_trades) / 
                           sum(t['realized_pnl'] for t in losing_trades)) if losing_trades else 0
        
        avg_r_multiple = np.mean([t['r_multiple'] for t in self.position_history])
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(win_rate * 100, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_r_multiple': round(avg_r_multiple, 2),
            'expectancy': round(avg_win * win_rate + avg_loss * (1 - win_rate), 2)
        }

# Singleton instance
risk_engine = InstitutionalRiskEngine()
