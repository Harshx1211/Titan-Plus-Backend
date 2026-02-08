"""
ENHANCED API ENDPOINTS
======================
Statistics and monitoring endpoints for outcome tracking.
"""

from fastapi import APIRouter
from typing import Dict, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger("api_enhanced")

# Create a router for outcome tracking endpoints
outcome_router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


@outcome_router.get("/statistics")
async def get_outcome_statistics() -> Dict:
    """
    Get comprehensive outcome statistics.
    
    Returns:
        {
            "total_tracked": 45,
            "win_rate": 62.5,
            "wins": 25,
            "losses": 15,
            "expired": 5,
            "monitoring": 3,
            "avg_win_pnl": 75.5,
            "avg_loss_pnl": 45.2,
            "profit_factor": 1.67
        }
    """
    try:
        from api import core
        
        # Access the global core object (ensure it's initialized)
        if not hasattr(core, 'outcome_tracker') or core.outcome_tracker is None:
            return {
                "error": "Outcome tracker not initialized",
                "total_tracked": 0,
                "win_rate": 0.0
            }
        
        stats = core.outcome_tracker.get_statistics()
        
        return {
            "success": True,
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@outcome_router.get("/recent")
async def get_recent_outcomes(limit: int = 10) -> Dict:
    """
    Get recent completed outcomes.
    
    Args:
        limit: Number of recent outcomes to return (default 10)
    
    Returns:
        {
            "outcomes": [
                {
                    "signal_id": "DEC_20260208_143022",
                    "symbol": "NIFTY28FEB2424500CE",
                    "direction": "CE",
                    "entry": 125.5,
                    "exit": 185.0,
                    "outcome": "WIN",
                    "pnl": 59.5,
                    "duration_hours": 2.5
                }
            ]
        }
    """
    try:
        from api import core
        
        if not hasattr(core, 'outcome_tracker') or core.outcome_tracker is None:
            return {
                "success": False,
                "error": "Outcome tracker not initialized"
            }
        
        outcomes = core.outcome_tracker.get_recent_outcomes(limit=limit)
        
        return {
            "success": True,
            "data": outcomes,
            "count": len(outcomes),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent outcomes: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@outcome_router.get("/monitoring")
async def get_monitoring_status() -> Dict:
    """
    Get detailed monitoring status for debugging.
    
    Returns:
        {
            "is_running": true,
            "active_monitors": 3,
            "completed_outcomes": 42,
            "signals_by_status": {...}
        }
    """
    try:
        from api import core
        
        if not hasattr(core, 'outcome_tracker') or core.outcome_tracker is None:
            return {
                "success": False,
                "error": "Outcome tracker not initialized"
            }
        
        status = core.outcome_tracker.get_monitoring_status()
        
        return {
            "success": True,
            "data": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@outcome_router.get("/performance/timeline")
async def get_performance_timeline(days: int = 7) -> Dict:
    """
    Get win rate and performance metrics over time.
    
    Args:
        days: Number of days to look back (default 7)
    
    Returns:
        {
            "timeline": [
                {
                    "date": "2026-02-08",
                    "signals": 5,
                    "wins": 3,
                    "losses": 2,
                    "win_rate": 60.0,
                    "total_pnl": 125.5
                }
            ]
        }
    """
    try:
        from api import core
        
        if not hasattr(core, 'outcome_tracker') or core.outcome_tracker is None:
            return {
                "success": False,
                "error": "Outcome tracker not initialized"
            }
        
        # Get all completed outcomes
        outcomes = core.outcome_tracker.completed_outcomes
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Group by date
        daily_data = defaultdict(lambda: {
            "signals": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0
        })
        
        for outcome in outcomes:
            if outcome.closed_at and outcome.closed_at >= cutoff:
                date_key = outcome.closed_at.date().isoformat()
                daily_data[date_key]["signals"] += 1
                
                if outcome.outcome == "WIN":
                    daily_data[date_key]["wins"] += 1
                    if outcome.exit_price:
                        daily_data[date_key]["total_pnl"] += (outcome.exit_price - outcome.entry_price)
                
                elif outcome.outcome == "LOSS":
                    daily_data[date_key]["losses"] += 1
                    if outcome.exit_price:
                        daily_data[date_key]["total_pnl"] += (outcome.exit_price - outcome.entry_price)
        
        # Calculate win rates
        timeline = []
        for date_str in sorted(daily_data.keys()):
            data = daily_data[date_str]
            win_rate = (data["wins"] / data["signals"] * 100) if data["signals"] > 0 else 0.0
            
            timeline.append({
                "date": date_str,
                "signals": data["signals"],
                "wins": data["wins"],
                "losses": data["losses"],
                "win_rate": round(win_rate, 2),
                "total_pnl": round(data["total_pnl"], 2)
            })
        
        return {
            "success": True,
            "data": {
                "timeline": timeline,
                "days": days
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance timeline: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@outcome_router.post("/manual_outcome")
async def log_manual_outcome(
    signal_id: str,
    outcome: str,  # WIN, LOSS, BREAKEVEN
    exit_price: float,
    notes: str = ""
) -> Dict:
    """
    Manually log an outcome (for signals executed outside the system).
    
    Args:
        signal_id: Signal ID
        outcome: WIN, LOSS, or BREAKEVEN
        exit_price: Actual exit price
        notes: Optional notes
    
    Returns:
        {"success": true, "message": "Outcome logged"}
    """
    try:
        from api import core
        
        if not hasattr(core, 'db') or core.db is None:
            return {
                "success": False,
                "error": "Database not initialized"
            }
        
        # Log to database
        core.db.log_outcome(signal_id, outcome, {
            "exit_price": exit_price,
            "notes": notes,
            "manual": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Manual outcome logged: {signal_id} -> {outcome} @ {exit_price}")
        
        return {
            "success": True,
            "message": f"Outcome logged for {signal_id}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to log manual outcome: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
