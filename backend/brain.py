from backend.engine import engine
from backend.smc_logic import smc_engine
from backend.database import db
from backend.ai_decision import ai_engine
from backend.risk_engine import risk_engine, PositionSide
import asyncio
import pandas as pd
from typing import Dict, Optional

class TitanBrain:
    """
    Titan Brain V3 - Institutional Intelligence Core
    Orchestrates SMC analysis, AI validation, and risk management
    """
    def __init__(self):
        self.is_running = False
        self.analysis_interval = 60  # seconds
        self.monitored_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.usd_to_inr = 83.0  # INR conversion rate
        
    async def run_247(self):
        """Main 24/7 monitoring loop"""
        self.is_running = True
        print("=" * 60)
        print("🧠 TITAN BRAIN V3 - INSTITUTIONAL INTELLIGENCE CORE")
        print("=" * 60)
        print(f"📊 Monitoring: {', '.join(self.monitored_symbols)}")
        print(f"🤖 AI Model: {ai_engine.model_version}")
        print(f"⚡ Analysis Interval: {self.analysis_interval}s")
        print("=" * 60)
        
        while self.is_running:
            try:
                for symbol in self.monitored_symbols:
                    await self._analyze_symbol(symbol)
                
                # Check active position status
                await self._monitor_active_position()
                
                await asyncio.sleep(self.analysis_interval)
                
            except Exception as e:
                print(f"❌ BRAIN ERROR: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)
    
    async def _analyze_symbol(self, symbol: str):
        """
        Complete analysis pipeline for a single symbol
        """
        # 1. Fetch market data
        df = await engine.fetch_data(symbol, timeframe='15m', limit=200)
        if df is None or len(df) < 100:
            return
        
        # 2. Run institutional SMC analysis
        smc_analysis = smc_engine.analyze_market_structure(df, timeframe='15m')
        
        # 3. Determine if there's a tradeable setup
        setup_type = self._identify_setup(smc_analysis)
        
        if setup_type is None:
            # No setup - just log the analysis
            db.log_brain_thought(
                symbol=symbol,
                sentiment="SCANNING",
                logic_details={
                    'confluence_score': smc_analysis['confluence_score'],
                    'trend_bias': str(smc_analysis['trend_bias']),
                    'regime': smc_analysis['market_regime']
                },
                market_regime=smc_analysis['market_regime']
            )
            return
        
        # 4. AI Validation
        is_valid, confidence, ai_metadata = ai_engine.validate_setup(
            symbol, setup_type, smc_analysis, df
        )
        
        # 5. Log the thought process
        db.log_brain_thought(
            symbol=symbol,
            sentiment=setup_type if is_valid else "FILTERED",
            logic_details={
                **ai_metadata['features'],
                'confluence_score': smc_analysis['confluence_score'],
                'ai_confidence': confidence,
                'setup_type': setup_type
            },
            market_regime=smc_analysis['market_regime']
        )
        
        # 6. Update market state
        current_price = df['close'].iloc[-1]
        db.update_market_state(symbol, current_price, df['volume'].iloc[-1])
        
        # 7. Generate advisory signal if validated
        if is_valid:
            await self._generate_advisory_signal(
                symbol, setup_type, current_price, smc_analysis, df, ai_metadata
            )
    
    def _identify_setup(self, smc_analysis: Dict) -> Optional[str]:
        """
        Identifies if there's a high-probability setup
        Returns: 'LONG', 'SHORT', or None
        """
        # Minimum confluence requirement
        if smc_analysis['confluence_score'] < 60:
            return None
        
        structure = smc_analysis['structure_breaks']
        trend = smc_analysis['trend_bias']
        
        # Bullish setup criteria
        if (structure.get('bos') == 'BOS_BULLISH' or structure.get('choch') == 'CHOCH_BULLISH'):
            if hasattr(trend, 'value') and trend.value in ['BULLISH', 'NEUTRAL']:
                return "LONG"
        
        # Bearish setup criteria
        if (structure.get('bos') == 'BOS_BEARISH' or structure.get('choch') == 'CHOCH_BEARISH'):
            if hasattr(trend, 'value') and trend.value in ['BEARISH', 'NEUTRAL']:
                return "SHORT"
        
        return None
    
    async def _generate_advisory_signal(self, symbol: str, setup_type: str, 
                                       entry_price: float, smc_analysis: Dict,
                                       market_data: pd.DataFrame, ai_metadata: Dict):
        """
        Generates a complete advisory signal with risk parameters
        """
        # Check if we can enter a new position
        can_enter, message = risk_engine.validate_new_position()
        if not can_enter:
            print(f"⚠️  BRAIN: {message}")
            return
        
        # Calculate risk parameters
        side = PositionSide.LONG if setup_type == "LONG" else PositionSide.SHORT
        risk_params = risk_engine.calculate_position_parameters(
            symbol, side, entry_price, market_data, smc_analysis
        )
        
        # Validate R:R ratio
        if risk_params.risk_reward_ratio < 2.0:
            print(f"⚠️  BRAIN: {symbol} setup rejected - R:R too low ({risk_params.risk_reward_ratio:.2f})")
            return
        
        # Convert to INR for display
        entry_inr = entry_price * self.usd_to_inr
        sl_inr = risk_params.stop_loss * self.usd_to_inr
        tp1_inr = risk_params.take_profit_1 * self.usd_to_inr
        tp2_inr = risk_params.take_profit_2 * self.usd_to_inr
        tp3_inr = risk_params.take_profit_3 * self.usd_to_inr
        
        # Log the advisory trade to Supabase
        trade_metadata = {
            **ai_metadata,
            'risk_params': {
                'stop_loss': risk_params.stop_loss,
                'tp1': risk_params.take_profit_1,
                'tp2': risk_params.take_profit_2,
                'tp3': risk_params.take_profit_3,
                'rr_ratio': risk_params.risk_reward_ratio
            },
            'confluence_score': smc_analysis['confluence_score']
        }
        
        db.log_trade(
            symbol=symbol,
            side=setup_type,
            entry_price=entry_price,
            entry_reason=f"SMC {setup_type} | Confluence: {smc_analysis['confluence_score']:.0f}% | AI: {ai_metadata['confidence']:.1%}"
        )
        
        # Open position in risk engine (for simulation tracking)
        try:
            position_id = risk_engine.open_position(
                symbol, side, risk_params, trade_metadata
            )
            print(f"\n✨ ADVISORY SIGNAL GENERATED ✨")
            print(f"📍 Symbol: {symbol} {setup_type}")
            print(f"💰 Entry: ₹{entry_inr:,.2f} | SL: ₹{sl_inr:,.2f}")
            print(f"🎯 Targets: ₹{tp1_inr:,.2f} / ₹{tp2_inr:,.2f} / ₹{tp3_inr:,.2f}")
            print(f"📊 R:R = 1:{risk_params.risk_reward_ratio:.2f}")
            print(f"📍 Position ID: {position_id}")
        except Exception as e:
            print(f"❌ Failed to open position: {e}")
    
    async def _monitor_active_position(self):
        """
        Monitors active position and manages exits
        """
        if not risk_engine.active_position:
            return
        
        pos = risk_engine.active_position
        symbol = pos['symbol']
        
        # Fetch current price
        df = await engine.fetch_data(symbol, timeframe='1m', limit=1)
        if df is None:
            return
        
        current_price = df['close'].iloc[-1]
        
        # Check position status
        status = risk_engine.check_position_status(current_price)
        
        if status['status'] == 'STOP_HIT':
            # Close position at stop loss
            summary = risk_engine.close_position(current_price, "Stop Loss Hit")
            pnl_inr = summary['realized_pnl'] * self.usd_to_inr
            
            print(f"🛑 STOP LOSS HIT: {symbol}")
            print(f"   P&L: ₹{pnl_inr:,.2f} ({summary['r_multiple']:.2f}R)")
            
            # Log outcome to AI engine for learning
            outcome = 'LOSS'
            ai_signal_id = pos['metadata'].get('signal_id')
            if ai_signal_id:
                ai_engine.log_outcome(ai_signal_id, outcome, summary['realized_pnl'])
            
            # Update Supabase
            db.close_trade(
                trade_id=pos['id'],
                exit_price=current_price,
                exit_reason="Stop Loss",
                pnl=summary['realized_pnl']
            )
        
        elif status['status'] == 'TARGET_HIT':
            # Partial or full exit at target
            for action in status['actions']:
                print(f"🎯 TARGET HIT: {action['target']} at ${action['price']}")
            
            # Check if all targets hit
            all_hit = all(tp['hit'] for tp in pos['targets'].values())
            if all_hit:
                summary = risk_engine.close_position(current_price, "All Targets Hit")
                pnl_inr = summary['realized_pnl'] * self.usd_to_inr
                
                print(f"🎉 ALL TARGETS HIT: {symbol}")
                print(f"   P&L: ₹{pnl_inr:,.2f} ({summary['r_multiple']:.2f}R)")
                
                outcome = 'WIN'
                ai_signal_id = pos['metadata'].get('signal_id')
                if ai_signal_id:
                    ai_engine.log_outcome(ai_signal_id, outcome, summary['realized_pnl'])
                
                db.close_trade(
                    trade_id=pos['id'],
                    exit_price=current_price,
                    exit_reason="Take Profit",
                    pnl=summary['realized_pnl']
                )
        
        elif status['status'] == 'ACTIVE':
            # Just monitoring
            if status.get('unrealized_pnl'):
                pnl_inr = status['unrealized_pnl'] * self.usd_to_inr
                pnl_emoji = "🟢" if status['unrealized_pnl'] > 0 else "🔴"
                print(f"{pnl_emoji} {symbol}: Unrealized P&L = ₹{pnl_inr:,.2f}")

titan_brain = TitanBrain()
