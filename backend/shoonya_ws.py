import logging
import json
import threading
import time
from typing import Dict, List, Callable, Optional
from infrastructure import MarketState
from providers import ShoonyaProvider

logger = logging.getLogger("shoonya_ws")

class ShoonyaWebSocket:
    """
    [Institutional Phase 6] Core WebSocket Provider.
    Handles real-time tick-by-tick data from Shoonya/Noren.
    """
    def __init__(self, provider: ShoonyaProvider, on_tick_callback: Optional[Callable] = None):
        self.provider = provider
        self.api = provider.api
        self.on_tick = on_tick_callback
        self.market_state = MarketState()
        self.is_connected = False
        self.subscribed_tokens: List[str] = []
        
        # Token to Symbol mapping for easy lookup
        self.token_map = {}
        for sym, (exch, token) in self.provider.index_tokens.items():
            self.token_map[f"{exch}|{token}"] = sym

    def start(self):
        """Initializes and starts the websocket connection."""
        if not self.provider.authenticated:
            if not self.provider.login():
                logger.error("SHOONYA_WS: Failed to authenticate provider.")
                return False

        try:
            # NorenApi uses these callbacks
            self.api.start_websocket(
                subscribe_callback=self._on_tick,
                socket_open_callback=self._on_open,
                socket_error_callback=self._on_error,
                socket_close_callback=self._on_close
            )
            return True
        except Exception as e:
            logger.error(f"SHOONYA_WS: Connection attempt failed: {e}")
            return False

    def _on_open(self):
        self.is_connected = True
        logger.info("SHOONYA_WS: Connection opened. Subscribing to tokens...")
        self.resubscribe()

    def _on_error(self, err):
        logger.error(f"SHOONYA_WS: Socket error: {err}")

    def _on_close(self):
        self.is_connected = False
        logger.warning("SHOONYA_WS: Connection closed.")

    def resubscribe(self):
        """Subscribes to all managed indices and futures."""
        if not self.is_connected: return
        
        # Subscribe to Indices
        for sym, (exch, token) in self.provider.index_tokens.items():
            self.subscribe(exch, token, sym)
            
        # Subscribe to Futures
        for sym, (exch, token) in self.provider.future_tokens.items():
            self.subscribe(exch, token, f"{sym}_FUT")

    def subscribe(self, exchange: str, token: str, symbol: str):
        """Subscribes to a specific instrument."""
        if not self.is_connected: return
        
        instrument = f"{exchange}|{token}"
        self.token_map[instrument] = symbol
        
        logger.info(f"SHOONYA_WS: Subscribing to {symbol} ({instrument})")
        self.api.subscribe(instrument)

    def _on_tick(self, tick: Dict):
        """
        Handle incoming tick data.
        Institutional Rule: NO blocking I/O or heavy logic inside this callback.
        """
        try:
            # Basic parsing
            token = tick.get('tk')
            exch = tick.get('e')
            lp = tick.get('lp')
            
            if not token or lp is None: return
            
            instrument = f"{exch}|{token}"
            symbol = self.token_map.get(instrument)
            
            if not symbol: return
            
            tick_data = {
                'symbol': symbol,
                'lp': float(lp),
                'v': int(tick.get('v', 0)),
                'oi': int(tick.get('oi', 0)),
                'timestamp': time.time()
            }
            
            # 1. Update Atomic Market State
            self.market_state.update(tick_data)
            
            # 2. Trigger Event-Driven Callback if registered
            if self.on_tick:
                self.on_tick(tick_data)
                
        except Exception as e:
            # Low-level error suppression for HFT performance
            pass

    def stop(self):
        """Force close the websocket."""
        if self.is_connected:
            self.api.close_websocket()
            self.is_connected = False
