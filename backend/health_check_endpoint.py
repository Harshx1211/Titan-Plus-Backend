"""
SYSTEM HEALTH CHECK ENDPOINT
=============================
Provides comprehensive system health monitoring.
"""

from fastapi import APIRouter
from datetime import datetime, timezone
import logging
import psutil
import os

logger = logging.getLogger("health_check")

# Create router
health_router = APIRouter(prefix="/api/health", tags=["health"])


@health_router.get("/")
async def health_check_simple():
    """
    Simple health check for uptime monitoring.
    
    Returns:
        {"status": "healthy", "timestamp": "..."}
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "v10.2.0"
    }


@health_router.get("/detailed")
async def health_check_detailed():
    """
    Detailed health check with all system components.
    
    Returns comprehensive system status including:
    - Data providers status
    - Database connectivity
    - Brain engine status
    - Outcome tracker status
    - System resources
    - Background threads
    """
    try:
        from api import core, live_state
        
        health_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "v10.2.0",
            "environment": os.getenv("ENVIRONMENT", "DEVELOPMENT"),
            "overall_status": "healthy",
            "components": {}
        }
        
        issues = []
        
        # 1. Check Data Providers
        provider_status = _check_data_providers(core)
        health_data["components"]["data_providers"] = provider_status
        if provider_status["status"] != "healthy":
            issues.append("Data providers degraded")
        
        # 2. Check Database
        db_status = _check_database(core)
        health_data["components"]["database"] = db_status
        if db_status["status"] != "healthy":
            issues.append("Database connectivity issues")
        
        # 3. Check Brain Engine
        brain_status = _check_brain_engine(core)
        health_data["components"]["brain"] = brain_status
        if brain_status["status"] != "healthy":
            issues.append("Brain engine not initialized")
        
        # 4. Check Outcome Tracker
        tracker_status = _check_outcome_tracker(core)
        health_data["components"]["outcome_tracker"] = tracker_status
        if tracker_status["status"] != "healthy":
            issues.append("Outcome tracker not running")
        
        # 5. Check System Resources
        resource_status = _check_system_resources()
        health_data["components"]["system_resources"] = resource_status
        if resource_status["status"] != "healthy":
            issues.append("System resources critical")
        
        # 6. Check Background Threads
        thread_status = _check_background_threads()
        health_data["components"]["background_threads"] = thread_status
        if thread_status["status"] != "healthy":
            issues.append("Background threads not running")
        
        # 7. Check WebSocket
        ws_status = _check_websocket(core)
        health_data["components"]["websocket"] = ws_status
        if ws_status["status"] != "healthy":
            issues.append("WebSocket disconnected")
        
        # Determine overall status
        if issues:
            health_data["overall_status"] = "degraded"
            health_data["issues"] = issues
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "error",
            "error": str(e)
        }


def _check_data_providers(core):
    """Check status of data providers."""
    try:
        if not hasattr(core, 'data_provider'):
            return {
                "status": "unhealthy",
                "error": "Data provider not initialized"
            }
        
        return {
            "status": "healthy",
            "primary_provider": getattr(core.data_provider, 'name', 'unknown'),
            "last_fetch": datetime.now(timezone.utc).isoformat()
        }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def _check_database(core):
    """Check database connectivity."""
    try:
        if not hasattr(core, 'db') or core.db is None:
            return {
                "status": "unhealthy",
                "error": "Database manager not initialized"
            }
        
        return {
            "status": "healthy",
            "connected": True,
            "last_write": datetime.now(timezone.utc).isoformat()
        }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def _check_brain_engine(core):
    """Check brain engine status."""
    try:
        if not hasattr(core, 'brain') or core.brain is None:
            return {
                "status": "unhealthy",
                "error": "Brain not initialized"
            }
        
        return {
            "status": "healthy",
            "decision_threshold": core.brain.decision_threshold,
            "models_loaded": {
                "xgboost": core.brain.xgb_engine is not None,
                "rl": core.brain.rl_agent is not None,
                "smc": core.brain.smc_engine is not None
            },
            "governor_status": core.brain.governor.lock_status
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def _check_outcome_tracker(core):
    """Check outcome tracker status."""
    try:
        if not hasattr(core, 'outcome_tracker') or core.outcome_tracker is None:
            return {
                "status": "unhealthy",
                "error": "Outcome tracker not initialized"
            }
        
        is_running = core.outcome_tracker.is_running
        
        return {
            "status": "healthy" if is_running else "degraded",
            "is_running": is_running,
            "active_monitors": len(core.outcome_tracker.active_monitors),
            "completed_outcomes": len(core.outcome_tracker.completed_outcomes)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def _check_system_resources():
    """Check system resource usage."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # Determine status
        status = "healthy"
        warnings = []
        
        if cpu_percent > 80:
            status = "degraded"
            warnings.append(f"High CPU usage: {cpu_percent}%")
        
        if memory_percent > 85:
            status = "degraded"
            warnings.append(f"High memory usage: {memory_percent}%")
        
        if disk_percent > 90:
            status = "degraded"
            warnings.append(f"Low disk space: {disk_percent}% used")
        
        result = {
            "status": status,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "memory_available_gb": memory.available / (1024**3),
            "disk_percent": disk_percent,
            "disk_free_gb": disk.free / (1024**3)
        }
        
        if warnings:
            result["warnings"] = warnings
        
        return result
        
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e)
        }


def _check_background_threads():
    """Check status of background threads."""
    try:
        from infrastructure import global_sentinel
        
        thread_status = global_sentinel.get_status()
        
        all_healthy = all(thread_status.values())
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "threads": thread_status,
            "total_threads": len(thread_status),
            "healthy_threads": sum(thread_status.values())
        }
        
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e)
        }


def _check_websocket(core):
    """Check WebSocket connection status."""
    try:
        if not hasattr(core, 'ws') or core.ws is None:
            return {
                "status": "unhealthy",
                "error": "WebSocket not initialized"
            }
        
        is_connected = getattr(core.ws, 'is_connected', False)
        
        return {
            "status": "healthy" if is_connected else "degraded",
            "is_connected": is_connected,
            "subscribed_tokens": len(getattr(core.ws, 'token_map', {}))
        }
        
    except Exception as e:
        return {
            "status": "unknown",
            "error": str(e)
        }


@health_router.get("/metrics")
async def get_system_metrics():
    """
    Get real-time system metrics for monitoring.
    
    Returns:
        System metrics suitable for time-series monitoring
    """
    try:
        from api import core, live_state
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "active_signals": len(live_state.active_signals),
            "monitoring_signals": len(core.outcome_tracker.active_monitors) if hasattr(core, 'outcome_tracker') else 0,
            "total_outcomes": len(core.outcome_tracker.completed_outcomes) if hasattr(core, 'outcome_tracker') else 0,
            "websocket_connected": getattr(core.ws, 'is_connected', False) if hasattr(core, 'ws') else False
        }
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return {"error": str(e)}
