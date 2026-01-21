# =============================================================================
# Inventory Hub Orchestrator Package
# =============================================================================
# Phase 1: Secure File Ingestion Layer
#
# This orchestrator is the new central intelligence for SGA inventory
# file management, replacing the estoque orchestrator over time.
#
# Current capabilities (Phase 1):
# - Generate secure upload URLs (presigned POST)
# - Verify file uploads completed
# - Validate file types for inventory import
#
# Future phases:
# - Phase 2: CSV/Excel content parsing
# - Phase 3: LTM integration for learning patterns
# - Phase 4: Full estoque orchestrator replacement
#
# VERSION: 2026-01-21T18:00:00Z
# =============================================================================

from .main import app, create_inventory_hub, invoke, AGENT_ID, AGENT_NAME

__all__ = [
    "app",
    "create_inventory_hub",
    "invoke",
    "AGENT_ID",
    "AGENT_NAME",
]
