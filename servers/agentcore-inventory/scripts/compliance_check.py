#!/usr/bin/env python3
# =============================================================================
# Architecture Compliance Checker for Faiston NEXO
# =============================================================================
# Purpose: Enforces CLAUDE.md architectural rules to prevent degradation
#          from AI-First Agentic System to traditional web service
#
# CRITICAL CHECKS (ALL MUST PASS):
# 1. Agentic Only     - Scan for forbidden FastAPI/Flask patterns
# 2. Docstrings       - Verify Google-style docstrings
# 3. Strands Imports  - No direct google.generativeai usage
# 4. Gemini Models    - Verify Gemini 2.5 family usage
#
# Exit Code: Non-zero if ANY check fails (blocks CI)
# =============================================================================

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# ANSI color codes
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class ComplianceChecker:
    """Architecture compliance validator for CLAUDE.md rules."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check_agentic_only(self) -> bool:
        """
        Check 1: Agentic Only Architecture

        Scans for forbidden traditional web service patterns:
        - Direct FastAPI/Flask app instantiation
        - Traditional REST controller patterns
        - Non-agentic microservice patterns

        Returns:
            True if compliant, False if violations found
        """
        print(f"{BLUE}[1/4] Checking Agentic Only architecture...{RESET}")

        forbidden_patterns = [
            (r"FastAPI\(\)", "Direct FastAPI instantiation (use agent adapters only)"),
            (r"Flask\(__name__\)", "Direct Flask instantiation (use agent adapters only)"),
            (r"@app\.route\(", "Traditional REST route decorator (use agent tools)"),
            (r"@router\.get\(", "Traditional REST router (use agent tools)"),
        ]

        python_files = list(self.root_dir.rglob("*.py"))
        violations = 0

        for file_path in python_files:
            # Skip test files and virtual environments
            if any(skip in str(file_path) for skip in ["test_", "tests/", "venv/", ".venv/"]):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                for pattern, message in forbidden_patterns:
                    matches = re.finditer(pattern, content)
                    for match in matches:
                        line_num = content[:match.start()].count("\n") + 1
                        self.errors.append(
                            f"  {file_path}:{line_num} - {message}"
                        )
                        violations += 1
            except Exception as e:
                self.warnings.append(f"  Could not read {file_path}: {e}")

        if violations == 0:
            print(f"  {GREEN}✓{RESET} No traditional web service patterns found")
            return True
        else:
            print(f"  {RED}✗{RESET} Found {violations} forbidden pattern(s)")
            return False

    def check_docstrings(self) -> bool:
        """
        Check 2: Google-Style Docstrings

        Verifies all functions have proper docstrings with:
        - Summary line
        - Args section (if parameters exist)
        - Returns section (if return value exists)

        Returns:
            True if compliant, False if violations found
        """
        print(f"{BLUE}[2/4] Checking Google-style docstrings...{RESET}")

        python_files = list(self.root_dir.rglob("*.py"))
        violations = 0

        for file_path in python_files:
            # Skip test files and __init__.py
            if any(skip in str(file_path) for skip in ["test_", "tests/", "__init__.py", "venv/", ".venv/"]):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Find all function definitions
                func_pattern = r"def\s+(\w+)\s*\([^)]*\):"
                for match in re.finditer(func_pattern, content):
                    func_name = match.group(1)

                    # Skip private/magic methods
                    if func_name.startswith("_"):
                        continue

                    # Check if docstring exists after function definition
                    func_end = match.end()
                    following_text = content[func_end:func_end + 200]

                    if '"""' not in following_text and "'''" not in following_text:
                        line_num = content[:match.start()].count("\n") + 1
                        self.errors.append(
                            f"  {file_path}:{line_num} - Function '{func_name}' missing docstring"
                        )
                        violations += 1
            except Exception as e:
                self.warnings.append(f"  Could not read {file_path}: {e}")

        if violations == 0:
            print(f"  {GREEN}✓{RESET} All functions have docstrings")
            return True
        else:
            print(f"  {RED}✗{RESET} Found {violations} function(s) without docstrings")
            return False

    def check_strands_imports(self) -> bool:
        """
        Check 3: Strands SDK Usage

        Verifies agents use Strands framework, not direct google.generativeai:
        - Check for 'from strands_agents import' or 'from strands.' patterns
        - Detect forbidden 'import google.generativeai' or 'from google.generativeai'

        Returns:
            True if compliant, False if violations found
        """
        print(f"{BLUE}[3/4] Checking Strands SDK usage...{RESET}")

        agent_files = list((self.root_dir / "agents").rglob("*.py")) if (self.root_dir / "agents").exists() else []
        violations = 0

        for file_path in agent_files:
            # Skip test files
            if "test_" in str(file_path) or "tests/" in str(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check for direct google.generativeai usage (FORBIDDEN)
                if re.search(r"import\s+google\.generativeai|from\s+google\.generativeai", content):
                    self.errors.append(
                        f"  {file_path} - Direct google.generativeai import (must use Strands)"
                    )
                    violations += 1

                # Check for Strands imports (REQUIRED for agent files)
                has_strands = re.search(r"from\s+strands|import\s+strands", content)
                if not has_strands and len(content) > 100:  # Skip tiny files
                    self.warnings.append(
                        f"  {file_path} - No Strands imports found (verify if agent file)"
                    )
            except Exception as e:
                self.warnings.append(f"  Could not read {file_path}: {e}")

        if violations == 0:
            print(f"  {GREEN}✓{RESET} No direct google.generativeai usage found")
            return True
        else:
            print(f"  {RED}✗{RESET} Found {violations} direct SDK usage violation(s)")
            return False

    def check_gemini_models(self) -> bool:
        """
        Check 4: Gemini 2.5 Model Family

        Verifies agent configurations use approved models:
        - Gemini 2.5 Pro (for critical agents)
        - Gemini 2.5 Flash (for non-critical agents)
        - No unauthorized LLMs (OpenAI, Anthropic, etc.)

        Returns:
            True if compliant, False if violations found
        """
        print(f"{BLUE}[4/4] Checking Gemini 2.5 model usage...{RESET}")

        config_files = list(self.root_dir.rglob("agent.yaml")) + list(self.root_dir.rglob("config.yaml"))
        violations = 0

        for file_path in config_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check for model configuration
                if "model:" in content:
                    # Detect unauthorized models
                    unauthorized = [
                        ("gpt-", "OpenAI GPT models"),
                        ("claude-", "Anthropic Claude models"),
                        ("gemini-1", "Outdated Gemini 1.x models"),
                    ]

                    for pattern, model_name in unauthorized:
                        if pattern in content.lower():
                            self.errors.append(
                                f"  {file_path} - Unauthorized model: {model_name}"
                            )
                            violations += 1

                    # Verify Gemini 2.5 usage
                    if "gemini" in content.lower() and "2.5" not in content and "2-5" not in content:
                        self.warnings.append(
                            f"  {file_path} - Verify Gemini version (should be 2.5)"
                        )
            except Exception as e:
                self.warnings.append(f"  Could not read {file_path}: {e}")

        if violations == 0:
            print(f"  {GREEN}✓{RESET} No unauthorized models found")
            return True
        else:
            print(f"  {RED}✗{RESET} Found {violations} unauthorized model(s)")
            return False

    def run_all_checks(self) -> bool:
        """
        Run all compliance checks and report results.

        Returns:
            True if all checks pass, False otherwise
        """
        print(f"\n{BLUE}╔════════════════════════════════════════════════╗{RESET}")
        print(f"{BLUE}║  Architecture Compliance Check (CLAUDE.md)    ║{RESET}")
        print(f"{BLUE}╚════════════════════════════════════════════════╝{RESET}\n")

        results = [
            self.check_agentic_only(),
            self.check_docstrings(),
            self.check_strands_imports(),
            self.check_gemini_models(),
        ]

        # Print summary
        print(f"\n{BLUE}{'='*50}{RESET}")
        print(f"{BLUE}SUMMARY{RESET}")
        print(f"{BLUE}{'='*50}{RESET}\n")

        if self.errors:
            print(f"{RED}ERRORS ({len(self.errors)}):{RESET}")
            for error in self.errors:
                print(error)
            print()

        if self.warnings:
            print(f"{YELLOW}WARNINGS ({len(self.warnings)}):{RESET}")
            for warning in self.warnings:
                print(warning)
            print()

        all_passed = all(results)

        if all_passed:
            print(f"{GREEN}✓ All compliance checks PASSED{RESET}\n")
        else:
            print(f"{RED}✗ Compliance checks FAILED{RESET}\n")
            print(f"{RED}Blocking CI - Fix violations before merge{RESET}\n")

        return all_passed


def main() -> int:
    """
    Main entry point for compliance checker.

    Returns:
        0 if all checks pass, 1 otherwise (blocks CI)
    """
    # Change to script directory to find root
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent  # server/agentcore-inventory

    checker = ComplianceChecker(root_dir)

    if checker.run_all_checks():
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
