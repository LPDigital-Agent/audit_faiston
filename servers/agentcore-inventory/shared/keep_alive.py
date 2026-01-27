# =============================================================================
# Keep-Alive Manager - Prevent AgentCore 15-Minute Idle Timeout
# =============================================================================
# AgentCore runtimes go idle after 15 minutes of inactivity, causing cold
# starts on next invocation. This module provides heartbeat mechanisms to
# keep high-traffic agents warm.
#
# Usage:
#   from shared.keep_alive import KeepAliveManager
#
#   # In agent main.py
#   keep_alive = KeepAliveManager(agent_id="nexo_import")
#   keep_alive.start()  # Background heartbeat every 10 minutes
#
# Architecture Notes:
# - Self-ping on health endpoint (/health on port 9000)
# - Configurable interval (default: 10 minutes = 600 seconds)
# - Graceful failure handling (doesn't crash the agent)
# - Only enable for high-traffic agents to save resources
#
# Reference:
# - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle.html
# =============================================================================

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default interval (10 minutes - provides 5-minute buffer before 15m timeout)
DEFAULT_INTERVAL_SECONDS = 600

# Agents that should have keep-alive enabled by default
# These are high-traffic agents that benefit from staying warm
HIGH_TRAFFIC_AGENTS = {
    "nexo_import",
    "intake",
    "estoque_control",
    "learning",
    "validation",
}


class KeepAliveManager:
    """
    Sends periodic heartbeats to prevent 15-minute idle timeout.

    Critical for frequently-used agents like NexoImportAgent.

    Example:
        keep_alive = KeepAliveManager(agent_id="nexo_import")
        keep_alive.start()

        # Later, to stop:
        keep_alive.stop()
    """

    def __init__(
        self,
        agent_id: str,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        port: int = 9000,
        auto_enable: bool = True,
    ):
        """
        Initialize keep-alive manager.

        Args:
            agent_id: Agent identifier for logging
            interval_seconds: Heartbeat interval (default: 600 = 10 minutes)
            port: Health check port (default: 9000 for A2A)
            auto_enable: Only enable for high-traffic agents (default: True)
        """
        self.agent_id = agent_id
        self.interval = interval_seconds
        self.port = port
        self._task: Optional[asyncio.Task] = None
        self._running = False

        # Auto-enable based on agent traffic patterns
        if auto_enable:
            self._enabled = agent_id in HIGH_TRAFFIC_AGENTS
        else:
            self._enabled = True

        # Environment override
        env_var = os.environ.get("KEEP_ALIVE_ENABLED", "").lower()
        if env_var == "true":
            self._enabled = True
        elif env_var == "false":
            self._enabled = False

    async def _heartbeat_loop(self):
        """Internal heartbeat loop - runs until stopped."""
        # Lazy import httpx to avoid cold start penalty
        import httpx

        health_url = f"http://localhost:{self.port}/health"
        logger.info(f"[KeepAlive:{self.agent_id}] Started (interval={self.interval}s)")

        while self._running:
            try:
                await asyncio.sleep(self.interval)

                if not self._running:
                    break

                # Self-ping health endpoint
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(health_url)

                    if response.status_code == 200:
                        logger.debug(f"[KeepAlive:{self.agent_id}] Heartbeat OK")
                    else:
                        logger.warning(
                            f"[KeepAlive:{self.agent_id}] Heartbeat status={response.status_code}"
                        )

            except asyncio.CancelledError:
                logger.info(f"[KeepAlive:{self.agent_id}] Cancelled")
                break
            except (ConnectionError, OSError, TimeoutError) as e:
                # Exception categorization for heartbeat: Transient network errors
                # These are expected and the heartbeat will continue trying
                logger.debug(f"[KeepAlive:{self.agent_id}] Transient error (will retry): {e}")
            except Exception as e:
                # Exception categorization for heartbeat: Unexpected errors
                # These could be bugs in the heartbeat logic or unexpected states
                logger.warning(
                    f"[KeepAlive:{self.agent_id}] Unexpected heartbeat error "
                    f"(type={type(e).__name__}): {e}"
                )
                # Continue trying but track for debugging

        logger.info(f"[KeepAlive:{self.agent_id}] Stopped")

    def start(self, force_restart: bool = False):
        """
        Start background heartbeat task.

        Args:
            force_restart: If True, restart even if already running (default: False)
        """
        if not self._enabled:
            logger.info(
                f"[KeepAlive:{self.agent_id}] Disabled (not high-traffic agent)"
            )
            return

        # Exception categorization for heartbeat: Better handling of task states
        if self._task is not None:
            if not self._task.done():
                if force_restart:
                    logger.info(f"[KeepAlive:{self.agent_id}] Force-restarting (stopping current)")
                    self.stop()
                else:
                    logger.debug(f"[KeepAlive:{self.agent_id}] Already running (use force_restart=True to restart)")
                    return
            else:
                # Previous task finished - check if it failed
                try:
                    # This will raise if the task had an exception
                    self._task.result()
                    logger.debug(f"[KeepAlive:{self.agent_id}] Previous task completed normally, restarting")
                except asyncio.CancelledError:
                    logger.debug(f"[KeepAlive:{self.agent_id}] Previous task was cancelled, restarting")
                except Exception as prev_error:
                    logger.warning(
                        f"[KeepAlive:{self.agent_id}] Previous task crashed with error: {prev_error}. "
                        "Restarting heartbeat..."
                    )

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    def stop(self):
        """Stop heartbeat task gracefully."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            self._task = None

    @property
    def is_running(self) -> bool:
        """Check if keep-alive is currently running."""
        return self._running and self._task is not None and not self._task.done()


# =============================================================================
# Convenience function for agents
# =============================================================================


def start_keep_alive_if_needed(agent_id: str) -> Optional[KeepAliveManager]:
    """
    Convenience function to start keep-alive for an agent.

    Only starts for high-traffic agents unless KEEP_ALIVE_ENABLED=true.

    Args:
        agent_id: Agent identifier

    Returns:
        KeepAliveManager instance if started, None otherwise

    Example:
        # In agent main.py after app initialization
        keep_alive = start_keep_alive_if_needed("nexo_import")
    """
    manager = KeepAliveManager(agent_id=agent_id)

    if manager._enabled:
        manager.start()
        return manager

    return None
