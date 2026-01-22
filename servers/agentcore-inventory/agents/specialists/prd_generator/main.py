# =============================================================================
# PRD Generator Agent - LOCAL Development Tool
# =============================================================================
# Generates Mini-PRDs for the /feature TDD workflow.
#
# IMPORTANT: This is a LOCAL agent for Claude Code, NOT deployed to AgentCore.
# It runs directly in the development environment (not via A2A server).
#
# Model: Gemini 2.5 Pro (fallback from Gemini 3.0 due to Strands SDK limitations)
# Thinking: ENABLED (for consistent structured output)
#
# Usage:
#   from agents.specialists.prd_generator import generate_prd
#   prd = generate_prd(feature_description="...", codebase_context="...")
# =============================================================================

import os
import logging
from typing import Optional
from pathlib import Path

from strands import Agent

# Import shared utilities for model creation
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils import create_gemini_model, PRO_THINKING_AGENTS

# Register PRD generator as a thinking agent for consistent structured output
# (This is done at import time since this is a local agent, not A2A)
PRO_THINKING_AGENTS.add("prd_generator")

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# PRD Template (English per CLAUDE.md requirement)
# =============================================================================

PRD_SYSTEM_PROMPT = """You are an expert product manager and technical architect. Your task is to create a Mini-PRD (Product Requirements Document) for a software feature.

## Your Role
- Analyze the feature request and codebase context
- Produce a structured, actionable PRD in English
- Focus on clarity, testability, and implementation guidance

## PRD Structure (MANDATORY)

Always output the PRD in this exact markdown format:

```markdown
# PRD: [Feature Name]

## 1. Objective
- **What:** [Clear description of what this feature does]
- **Why:** [Business value, user benefit, or technical necessity]

## 2. Architecture
- **Files to create:** [List new files with brief purpose]
- **Files to modify:** [List existing files that need changes]
- **Dependencies:** [New packages, APIs, or external services needed]

## 3. Test Plan
| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| [Test case description] | [Example input] | [Expected result] |
| [Add 3-5 meaningful test cases] | | |

## 4. Risks
- **Breaking changes:** [Potential regressions or compatibility issues]
- **Security:** [Security considerations if any]
- **Performance:** [Performance impact if any]

## 5. Out of Scope
- [Explicitly list what this PRD does NOT cover]
- [This prevents scope creep]
```

## Guidelines
1. Be specific and actionable - avoid vague statements
2. Test cases should be concrete with real examples
3. Consider edge cases in the test plan
4. Identify dependencies that need to be installed
5. Flag any breaking changes upfront
6. Keep the PRD concise but complete

## Output Format
Return ONLY the markdown PRD. Do not include any preamble or explanation.
"""


class PRDGeneratorAgent:
    """
    Local PRD Generator Agent using Strands + Gemini.

    This agent generates Mini-PRDs for the /feature TDD workflow.
    It is designed to run locally in Claude Code, not deployed to AgentCore.

    Attributes:
        agent: Strands Agent instance with Gemini model

    Example:
        generator = PRDGeneratorAgent()
        prd = generator.generate(
            feature_description="Add password strength indicator",
            codebase_context="React/TypeScript frontend with Tailwind"
        )
    """

    def __init__(self):
        """Initialize the PRD generator with Gemini model."""
        logger.info("[PRDGeneratorAgent] Initializing local PRD generator...")

        # Create model using shared utilities (ensures consistent config)
        # Uses LazyGeminiModel for deferred connection
        self._model = create_gemini_model(agent_type="prd_generator")

        # Create Strands agent with PRD system prompt
        self._agent = Agent(
            model=self._model,
            system_prompt=PRD_SYSTEM_PROMPT,
        )

        logger.info("[PRDGeneratorAgent] Initialized successfully")

    def generate(
        self,
        feature_description: str,
        codebase_context: str,
        similar_features: Optional[str] = None,
        project_rules: Optional[str] = None,
    ) -> str:
        """
        Generate a Mini-PRD for the given feature.

        Args:
            feature_description: What the user wants to build
            codebase_context: Context about the codebase (tech stack, patterns)
            similar_features: Optional description of similar existing features
            project_rules: Optional project-specific rules from CLAUDE.md

        Returns:
            Markdown string containing the complete PRD

        Raises:
            RuntimeError: If PRD generation fails
        """
        logger.info(f"[PRDGeneratorAgent] Generating PRD for: {feature_description[:50]}...")

        # Build the prompt with all context
        prompt_parts = [
            "## Feature Request",
            feature_description,
            "",
            "## Codebase Context",
            codebase_context,
        ]

        if similar_features:
            prompt_parts.extend([
                "",
                "## Similar Existing Features",
                similar_features,
            ])

        if project_rules:
            prompt_parts.extend([
                "",
                "## Project Rules (from CLAUDE.md)",
                project_rules,
            ])

        prompt_parts.extend([
            "",
            "---",
            "Based on the above information, generate a complete Mini-PRD.",
        ])

        prompt = "\n".join(prompt_parts)

        try:
            # Invoke the agent
            result = self._agent(prompt)

            # Extract the response text
            # Strands returns AgentResult with message attribute
            if hasattr(result, 'message'):
                prd_content = str(result.message)
            else:
                prd_content = str(result)

            logger.info("[PRDGeneratorAgent] PRD generated successfully")
            return prd_content

        except Exception as e:
            logger.error(f"[PRDGeneratorAgent] PRD generation failed: {e}")
            raise RuntimeError(f"Failed to generate PRD: {e}") from e


# =============================================================================
# Convenience Function for Direct Usage
# =============================================================================

_agent_instance: Optional[PRDGeneratorAgent] = None


def generate_prd(
    feature_description: str,
    codebase_context: str,
    similar_features: Optional[str] = None,
    project_rules: Optional[str] = None,
) -> str:
    """
    Generate a Mini-PRD for a feature (convenience function).

    This function provides a simple interface for the /feature command.
    It creates a singleton PRDGeneratorAgent instance on first call.

    Args:
        feature_description: What the user wants to build
        codebase_context: Context about the codebase (tech stack, patterns)
        similar_features: Optional description of similar existing features
        project_rules: Optional project-specific rules from CLAUDE.md

    Returns:
        Markdown string containing the complete PRD

    Example:
        prd = generate_prd(
            feature_description="Add password strength indicator to registration",
            codebase_context="React/TypeScript with Tailwind CSS"
        )
    """
    global _agent_instance

    # Lazy initialization of agent (deferred model connection)
    if _agent_instance is None:
        _agent_instance = PRDGeneratorAgent()

    return _agent_instance.generate(
        feature_description=feature_description,
        codebase_context=codebase_context,
        similar_features=similar_features,
        project_rules=project_rules,
    )


# =============================================================================
# CLI Entry Point (for testing)
# =============================================================================

if __name__ == "__main__":
    """
    Simple CLI for testing the PRD generator.

    Usage:
        python main.py "Add user authentication"
    """
    import sys

    if len(sys.argv) < 2:
        print("Usage: python main.py <feature_description>")
        print("Example: python main.py 'Add password strength indicator'")
        sys.exit(1)

    feature = " ".join(sys.argv[1:])

    print(f"Generating PRD for: {feature}")
    print("-" * 50)

    prd = generate_prd(
        feature_description=feature,
        codebase_context="Default codebase context for testing",
    )

    print(prd)
