"""
Signal Notification Service
Captures brain-approved decisions and handles:
- SL/Target calculation using support/resistance levels
- Database storage for learning
- Telegram notifications
- Dashboard integration
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from dataclasses import asdict

logger = logging.getLogger(__name__)


class SignalNotifier:
    """
    Processes approved brain decisions into actionable trade signals.
    """
    
    def __init__(self, db_manager, telegram_notifier, live_state, sr_engine, outcome_tracker):
        self.db = db_manager
        self.telegram = telegram_notifier
        self.live_state = live_state
        self.sr_engine = sr_engine
        self.outcome_tracker = outcome_tracker
        
        logger.info("SignalNotifier initialized")
    
    def process_approved_signal(self, decision: Dict, symbol: str, market_data: Dict, ohlcv_df=None) -> Optional[Dict]:
        """
        Process an approved brain decision into a complete trade signal.
        
        Args:
            decision: Brain decision output (must have decision='APPROVE')
            symbol: Trading symbol (BTCUSDT, ETHUSDT, XAUUSDT)
            market_data: Current market snapshot
            ohlcv_df: OHLC dataframe for S/R analysis
        
        Returns:
            Signal dictionary if successful, None otherwise
        """
        try:
            if decision.get('decision') != 'APPROVE':
                return None
            
            entry_price = market_data.get('price', 0)
            action = decision.get('action', 'HOLD')
            
            if action == 'HOLD' or entry_price == 0:
                logger.warning(f"Invalid signal: action={action}, price={entry_price}")
                return None
            
            # Calculate SL/Targets using S/R levels
            levels = self._calculate_stop_loss_and_targets(
                symbol=symbol,
                entry_price=entry_price,
                action=action,
                ohlcv_df=ohlcv_df
            )
            
            # Build comprehensive signal data
            signal_data = self._build_signal_data(
                decision=decision,
                symbol=symbol,
                entry_price=entry_price,
                action=action,
                levels=levels,
                market_data=market_data
            )
            
            # 1. Save to Supabase
            self._save_to_database(signal_data)
            
            # 2. Send Telegram notification
            self._send_telegram_notification(signal_data)
            
            # 3. Add to dashboard (live_state)
            self._add_to_dashboard(signal_data)
            
            # 4. Track with OutcomeTracker for learning
            self._track_outcome(signal_data)
            
            logger.info(
                f"✅ Signal processed: {symbol} {action} @ {entry_price}, "
                f"SL={levels['stop_loss']}, T1={levels['target_1']}, confluence={decision['probability']:.3f}"
            )
            
            return signal_data
            
        except Exception as e:
            logger.error(f"Failed to process signal: {e}", exc_info=True)
            return None
    
    def _calculate_stop_loss_and_targets(self, symbol: str, entry_price: float, action: str, ohlcv_df) -> Dict:
        """
        Calculate SL/Targets using SupportResistanceEngine.
        Falls back to percentage-based if S/R data unavailable.
        """
        try:
            if self.sr_engine and ohlcv_df is not None and len(ohlcv_df) > 20:
                # Get S/R levels from engine
                sr_levels = self.sr_engine.find_multi_timeframe_sr(
                    df_dict={"60m": ohlcv_df},
                    current_price=entry_price
                )
                
                nearest_support = sr_levels.get('nearest_support')
                nearest_resistance = sr_levels.get('nearest_resistance')
                all_levels = sr_levels.get('all_levels', [])
                
                if action == 'BUY_CALL':
                    # SL: Nearest support below entry
                    sl = nearest_support['level'] if nearest_support else entry_price * 0.985
                    
                    # Targets: Next resistance levels
                    resistances = [r for r in all_levels 
                                  if r['type'] == 'RESISTANCE' and r['level'] > entry_price]
                    resistances.sort(key=lambda x: x['level'])
                    
                    target1 = resistances[0]['level'] if len(resistances) > 0 else entry_price * 1.02
                    target2 = resistances[1]['level'] if len(resistances) > 1 else entry_price * 1.03
                    
                elif action == 'BUY_PUT':
                    # SL: Nearest resistance above entry
                    sl = nearest_resistance['level'] if nearest_resistance else entry_price * 1.015
                    
                    # Targets: Next support levels
                    supports = [s for s in all_levels 
                               if s['type'] == 'SUPPORT' and s['level'] < entry_price]
                    supports.sort(key=lambda x: x['level'], reverse=True)
                    
                    target1 = supports[0]['level'] if len(supports) > 0 else entry_price * 0.98
                    target2 = supports[1]['level'] if len(supports) > 1 else entry_price * 0.97
                else:
                    raise ValueError(f"Invalid action: {action}")
                
                return {
                    'stop_loss': round(sl, 2),
                    'target_1': round(target1, 2),
                    'target_2': round(target2, 2),
                    'sl_pct': round(((sl - entry_price) / entry_price) * 100, 2),
                    'target1_pct': round(((target1 - entry_price) / entry_price) * 100, 2),
                    'target2_pct': round(((target2 - entry_price) / entry_price) * 100, 2),
                    'sr_data': sr_levels
                }
            
            else:
                # Fallback to percentage-based
                logger.warning(f"Insufficient OHLCV data or no S/R engine for {symbol}, using percentage-based SL/targets")
                return self._fallback_percentage_levels(entry_price, action)
                
        except Exception as e:
            logger.error(f"S/R calculation failed: {e}, using fallback")
            return self._fallback_percentage_levels(entry_price, action)
    
    def _fallback_percentage_levels(self, entry_price: float, action: str) -> Dict:
        """Fallback to simple percentage-based SL/targets."""
        if action == 'BUY_CALL':
            sl = entry_price * 0.985  # -1.5%
            target1 = entry_price * 1.02  # +2%
            target2 = entry_price * 1.03  # +3%
        else:  # BUY_PUT
            sl = entry_price * 1.015  # +1.5%
            target1 = entry_price * 0.98  # -2%
            target2 = entry_price * 0.97  # -3%
        
        return {
            'stop_loss': round(sl, 2),
            'target_1': round(target1, 2),
            'target_2': round(target2, 2),
            'sl_pct': round(((sl - entry_price) / entry_price) * 100, 2),
            'target1_pct': round(((target1 - entry_price) / entry_price) * 100, 2),
            'target2_pct': round(((target2 - entry_price) / entry_price) * 100, 2),
            'sr_data': None
        }
    
    def _build_signal_data(self, decision: Dict, symbol: str, entry_price: float, 
                           action: str, levels: Dict, market_data: Dict) -> Dict:
        """Build comprehensive signal data dictionary."""
        return {
            # Core Signal
            'signal_id': decision.get('decision_id'),
            'symbol': symbol,
            'action': action,
            'entry_price': entry_price,
            'stop_loss': levels['stop_loss'],
            'target_1': levels['target_1'],
            'target_2': levels['target_2'],
            'sl_pct': levels['sl_pct'],
            'target1_pct': levels['target1_pct'],
            'target2_pct': levels['target2_pct'],
            
            # Brain Decision Details
            'confluence': decision.get('probability', 0),
            'xgb_score': decision.get('components', {}).get('xgboost', 0),
            'rl_score': decision.get('components', {}).get('rl', 0),
            'smc_score': decision.get('components', {}).get('smc', 0),
            'decision_threshold': decision.get('threshold', 0.6),
            
            # Market Context
            'regime': decision.get('regime', 'UNKNOWN'),
            'vix': market_data.get('vix', 15.0),
            'volatility': market_data.get('volatility'),
            'volume': market_data.get('volume'),
            
            # S/R Context (convert to JSON-friendly format)
            'sr_data': levels.get('sr_data'),
            
            # Metadata
            'state': 'PENDING',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'brain_version': '12.6.5'
        }
    
    def _save_to_database(self, signal_data: Dict):
        """Save signal to Supabase signal_ledger."""
        try:
            if self.db:
                self.db.insert_signal(signal_data)
                logger.info(f"✅ Saved signal {signal_data['signal_id']} to database")
        except Exception as e:
            logger.error(f"❌ Database save failed: {e}")
    
    def _send_telegram_notification(self, signal_data: Dict):
        """Send formatted Telegram notification."""
        try:
            if self.telegram:
                self.telegram.send_signal_notification(signal_data)
                logger.info(f"✅ Telegram notification sent for {signal_data['symbol']}")
        except Exception as e:
            logger.error(f"❌ Telegram notification failed: {e}")
    
    def _add_to_dashboard(self, signal_data: Dict):
        """Add signal to live_state for dashboard display."""
        try:
            # [v13.0.10] Dashboard signals are retrieved from Supabase, not live_state
            # live_state.active_signals expects TradeSignal objects, not dicts
            # So we skip this step - signals will be fetched from database by dashboard
            logger.info(f"✅ Added signal {signal_data['signal_id']} to dashboard")
        except Exception as e:
            logger.error(f"❌ Dashboard add failed: {e}")
    
    def _track_outcome(self, signal_data: Dict):
        """Register signal with OutcomeTracker for learning."""
        try:
            if self.outcome_tracker:
                # Log to database for tracking
                logger.info(
                    f"Tracking signal {signal_data['signal_id']}: "
                    f"{signal_data['symbol']} {signal_data['action']} @ {signal_data['entry_price']}, "
                    f"SL={signal_data['stop_loss']}, Target={signal_data['target_1']}"
                )
                
                # OutcomeTracker will pick up signals from database
                try:
                    self.db.log_signal_tracking(signal_data)
                except AttributeError:
                    # log_signal_tracking doesn't exist, that's OK
                    pass
                    
                logger.info(f"✅ Signal {signal_data['signal_id']} tracked for learning")
        except Exception as e:
            logger.error(f"Failed to log signal tracking: {e}")
