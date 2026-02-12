"""
WEBSOCKET RESILIENCE (v15.3.8 - Industrial Hardening)
=====================================================
Features:
- Watchdog for monitoring connection health
- Automatic reconnection logic
- Heartbeat tracking
- Re-subscription of tokens after reconnect
"""

import time
import logging
import threading
from typing import Callable, List, Optional

logger = logging.getLogger("ws_resilience")

class WebSocketWatchdog:
    """
    [v15.3.8] Monitors WebSocket health and triggers reconnections.
    """
    
    def __init__(self, 
                 reconnect_callback: Callable,
                 heartbeat_timeout: float = 10.0,
                 check_interval: float = 2.0):
        """
        Args:
            reconnect_callback: Function to call to trigger a reconnect
            heartbeat_timeout: Max seconds without message before reconnect
            check_interval: Interval to check health
        """
        self.reconnect_callback = reconnect_callback
        self.heartbeat_timeout = heartbeat_timeout
        self.check_interval = check_interval
        
        self.last_heartbeat = time.time()
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.reconnect_count = 0
        self.last_reconnect_time = 0
        
        logger.info(
            f"WebSocketWatchdog initialized (timeout={heartbeat_timeout}s, interval={check_interval}s)"
        )
    
    def start(self):
        """Start the watchdog monitor"""
        if self.is_running:
            return
            
        self.is_running = True
        self.last_heartbeat = time.time()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("WebSocketWatchdog thread started")
    
    def stop(self):
        """Stop the watchdog monitor"""
        self.is_running = False
        if self.monitor_thread:
            # We don't join to avoid blocking, it's a daemon thread
            self.monitor_thread = None
        logger.info("WebSocketWatchdog stopped")
    
    def notify_alive(self):
        """Reset the heartbeat timer"""
        self.last_heartbeat = time.time()
    
    def _monitor_loop(self):
        """Background loop to check for timeouts"""
        while self.is_running:
            try:
                age = time.time() - self.last_heartbeat
                
                if age > self.heartbeat_timeout:
                    # Skip if we literally just reconnected (give it 15s grace)
                    if time.time() - self.last_reconnect_time < 15:
                        time.sleep(self.check_interval)
                        continue
                        
                    logger.critical(
                        f"🚨 WS_SILENCE_DETECTED: No message for {age:.1f}s. "
                        f"Triggering reconnection (Total reconnections: {self.reconnect_count + 1})"
                    )
                    
                    self.reconnect_count += 1
                    self.last_reconnect_time = time.time()
                    
                    # Trigger reconnect in a separate thread to not block watchdog
                    threading.Thread(target=self.reconnect_callback, daemon=True).start()
                    
                    # Reset heartbeat to prevent immediate double-trigger
                    self.last_heartbeat = time.time()
                
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"WebSocketWatchdog error: {e}")
                time.sleep(self.check_interval)

class ConnectionHealth:
    """Tracks connection uptime and quality metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.total_messages = 0
        self.last_message_time = 0
        self.latency_samples: List[float] = []
        self.disconnections = 0
    
    def record_message(self, latency: Optional[float] = None):
        self.total_messages += 1
        self.last_message_time = time.time()
        if latency is not None:
            self.latency_samples.append(latency)
            if len(self.latency_samples) > 100:
                self.latency_samples.pop(0)
    
    def record_disconnect(self):
        self.disconnections += 1
    
    def get_stats(self) -> dict:
        uptime = time.time() - self.start_time
        avg_latency = sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0
        
        return {
            "uptime_seconds": uptime,
            "total_messages": self.total_messages,
            "disconnections": self.disconnections,
            "avg_latency_ms": avg_latency * 1000,
            "messages_per_second": self.total_messages / uptime if uptime > 0 else 0
        }

# Logic for re-subscribing after reconnect
def generate_resubscribe_payload(tokens: List[str], channel: str = "depth") -> dict:
    """Helper to generate subscription payloads for broker APIs"""
    # Specifically for Shoonya/Finvasia style
    if not tokens:
        return {}
        
    return {
        "t": "d" if channel == "depth" else "t",
        "k": "#".join(tokens)
    }
