# =============================================================================
# Faiston SGA Configuration Module
# =============================================================================
# Centralized configuration for agent ecosystem.
# =============================================================================

from .agent_urls import SPECIALIST_URLS, RUNTIME_IDS, get_agent_url

__all__ = ["SPECIALIST_URLS", "RUNTIME_IDS", "get_agent_url"]
