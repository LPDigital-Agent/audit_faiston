# =============================================================================
# ObservationAgent Tools
# =============================================================================
# Deterministic tools for the ObservationAgent.
# Following TOOL-FIRST principle: Python handles queries, LLM synthesizes.
#
# Tool Categories:
# 1. Memory Scanning - Read from AgentCore Memory
# 2. Pattern Analysis - Detect patterns with confidence scoring
# 3. Insight Generation - Create InsightReports with deduplication
# 4. Database Health - Query inventory for anomalies
# =============================================================================

from agents.specialists.observation.tools.scan_recent_activity import scan_recent_activity
from agents.specialists.observation.tools.analyze_patterns import analyze_patterns
from agents.specialists.observation.tools.generate_insight import generate_insight, dismiss_insight
from agents.specialists.observation.tools.check_inventory_health import check_inventory_health

__all__ = [
    "scan_recent_activity",
    "analyze_patterns",
    "generate_insight",
    "dismiss_insight",
    "check_inventory_health",
]
