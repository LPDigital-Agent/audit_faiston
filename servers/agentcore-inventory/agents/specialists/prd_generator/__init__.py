# =============================================================================
# PRD Generator Agent - LOCAL Development Tool
# =============================================================================
# Generates Mini-PRDs for the /feature TDD workflow.
#
# IMPORTANT: This is a LOCAL agent for Claude Code, NOT deployed to AgentCore.
# Uses Gemini 3.0 with fallback to Gemini 2.5.
#
# Usage:
#   from agents.specialists.prd_generator import generate_prd
#   prd = generate_prd(feature_description="...", codebase_context="...")
# =============================================================================

from .main import generate_prd, PRDGeneratorAgent

__all__ = ["generate_prd", "PRDGeneratorAgent"]
