# =============================================================================
# Faiston SGA Agent Ecosystem
# =============================================================================
# Structure: ADR-002 "Everything is an Agent" Architecture
#
# agents/
# ├── orchestrators/    # Domain orchestrators (full Strands Agents)
# │   └── estoque/      # Inventory management orchestrator
# └── specialists/      # Reusable specialist agents (15 total)
#
# IMPORTANT: AgentCore has a 30-second cold start limit.
# All agent imports must be LAZY (inside handler functions).
# Adding imports here will break the deployment.
# =============================================================================

# =============================================================================
# Ensure deployment root in sys.path
# =============================================================================
# AgentCore deploys code to /var/task, and this SHOULD be in sys.path.
# However, when importing from nested packages (e.g., agents/tools/intake_tools.py
# trying to import from root tools/s3_client.py), Python may not find it.
#
# This explicit path setup ensures the deployment root is always searchable,
# allowing absolute imports like `from core_tools.s3_client import ...` to work.
#
# NOTE: This is NOT a heavy import - just path manipulation (< 1ms).
# It doesn't violate the "lazy imports" principle.
# =============================================================================
import os
import sys

# LAMBDA_TASK_ROOT is set by AWS Lambda/AgentCore to /var/task
# Fallback to current directory for local development
_deployment_root = os.environ.get("LAMBDA_TASK_ROOT", os.getcwd())

# Ensure deployment root is at the beginning of sys.path for import priority
if _deployment_root not in sys.path:
    sys.path.insert(0, _deployment_root)
