#!/usr/bin/env python3
# =============================================================================
# AgentCore Identity Compliance Validation Script
# =============================================================================
# This script scans the codebase for legacy authentication patterns that
# violate AgentCore Identity best practices.
#
# Usage:
#   python scripts/cleanup_legacy_auth.py
#   python scripts/cleanup_legacy_auth.py --fix  # Show fix suggestions
#   python scripts/cleanup_legacy_auth.py --strict  # Exit 1 on any violation
#
# Reference:
# - docs/AgentCore/Identity_Implementation_guide.md
# - server/agentcore-inventory/shared/identity_utils.py
#
# Compliance Target: AgentCore Identity v1.0
# =============================================================================

import os
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class Severity(Enum):
    """Violation severity levels."""
    CRITICAL = "CRITICAL"  # Security vulnerability at entrypoint
    HIGH = "HIGH"          # Non-compliant pattern
    MEDIUM = "MEDIUM"      # Deprecated pattern (pass-through)
    LOW = "LOW"            # Style/best practice
    INFO = "INFO"          # Informational only


@dataclass
class Violation:
    """Represents a compliance violation."""
    file_path: str
    line_number: int
    pattern_name: str
    matched_text: str
    severity: Severity
    fix_suggestion: Optional[str] = None


# =============================================================================
# Context Detection
# =============================================================================

def is_in_docstring(content: str, line_num: int) -> bool:
    """Check if line is inside a docstring."""
    lines = content.split('\n')
    in_docstring = False
    docstring_char = None

    for i, line in enumerate(lines[:line_num], 1):
        stripped = line.strip()
        # Check for docstring delimiters
        if '"""' in stripped or "'''" in stripped:
            if not in_docstring:
                # Starting docstring
                in_docstring = True
                docstring_char = '"""' if '"""' in stripped else "'''"
                # Check if single-line docstring
                if stripped.count(docstring_char) >= 2:
                    in_docstring = False
            else:
                # Ending docstring
                if docstring_char in stripped:
                    in_docstring = False

    return in_docstring


def is_in_template_builder(content: str, line_num: int) -> bool:
    """Check if line is inside a template builder function (_build_message, etc.)."""
    lines = content.split('\n')
    # Look backward for function definition
    for i in range(line_num - 1, max(0, line_num - 50), -1):
        line = lines[i] if i < len(lines) else ""
        if re.match(r'^def\s+_build_message\s*\(', line):
            return True
        if re.match(r'^def\s+', line) and '_build_message' not in line:
            # Found a different function, stop
            return False
    return False


def is_internal_passthrough(content: str, line_num: int) -> bool:
    """Check if line is in an internal handler (pass-through pattern)."""
    lines = content.split('\n')
    # Look backward for function definition
    for i in range(line_num - 1, max(0, line_num - 30), -1):
        line = lines[i] if i < len(lines) else ""
        # Internal handlers start with _handle_ or _nexo_
        if re.match(r'^async\s+def\s+(_handle_|_nexo_)', line):
            return True
        if re.match(r'^def\s+(_handle_|_nexo_)', line):
            return True
        if re.match(r'^(async\s+)?def\s+', line):
            # Found a different function, stop
            return False
    return False


def is_entrypoint_function(content: str, line_num: int) -> bool:
    """Check if line is in an entrypoint function (requires validation)."""
    lines = content.split('\n')
    # Look backward for @app.entrypoint decorator
    for i in range(line_num - 1, max(0, line_num - 20), -1):
        line = lines[i] if i < len(lines) else ""
        if '@app.entrypoint' in line:
            return True
        if re.match(r'^def\s+invoke_sga_inventory\s*\(', line):
            return True
        if re.match(r'^(async\s+)?def\s+agent_invocation\s*\(', line):
            return True
        if re.match(r'^(async\s+)?def\s+', line):
            # Found a different function, stop
            return False
    return False


# =============================================================================
# Main Scanning Logic
# =============================================================================

def scan_file(file_path: str, content: str) -> List[Violation]:
    """Scan a single file for legacy patterns."""
    violations = []
    lines = content.split('\n')
    file_name = os.path.basename(file_path)

    # Skip non-agent files
    skip_files = ["identity_utils.py", "cleanup_legacy_auth.py", "oauth_decorators.py"]
    if file_name in skip_files:
        return violations

    # Pattern 1: Assignment from payload.get("user_id", ...)
    pattern = r'user_id\s*=\s*payload\.get\s*\(\s*["\']user_id["\']'

    for line_num, line in enumerate(lines, 1):
        match = re.search(pattern, line)
        if not match:
            continue

        # Skip if in docstring
        if is_in_docstring(content, line_num):
            continue

        # Skip if in template builder
        if is_in_template_builder(content, line_num):
            continue

        # Determine severity based on context
        if is_entrypoint_function(content, line_num):
            # CRITICAL: Direct entrypoint should use identity_utils
            violations.append(Violation(
                file_path=file_path,
                line_number=line_num,
                pattern_name="entrypoint_payload_user_id",
                matched_text=match.group(0)[:60],
                severity=Severity.CRITICAL,
                fix_suggestion="Use extract_user_identity(context, payload) from shared.identity_utils",
            ))
        elif is_internal_passthrough(content, line_num):
            # INFO: Internal pass-through - user_id already validated at entrypoint
            violations.append(Violation(
                file_path=file_path,
                line_number=line_num,
                pattern_name="passthrough_user_id",
                matched_text=match.group(0)[:60],
                severity=Severity.INFO,
                fix_suggestion="(Pass-through pattern - user_id validated at entrypoint. Consider passing user_id as parameter.)",
            ))
        else:
            # MEDIUM: Unclear context
            violations.append(Violation(
                file_path=file_path,
                line_number=line_num,
                pattern_name="unclear_payload_user_id",
                matched_text=match.group(0)[:60],
                severity=Severity.MEDIUM,
                fix_suggestion="Review context - ensure user_id is validated at entrypoint before pass-through",
            ))

    # Check for identity_utils usage in agent main.py files
    if "/agents/" in file_path and file_path.endswith("/main.py"):
        if "@app.entrypoint" in content or "def agent_invocation" in content:
            if "from shared.identity_utils import" not in content:
                violations.append(Violation(
                    file_path=file_path,
                    line_number=1,
                    pattern_name="missing_identity_utils_import",
                    matched_text="(import not found)",
                    severity=Severity.HIGH,
                    fix_suggestion="Add: from shared.identity_utils import extract_user_identity, log_identity_context",
                ))
            elif "extract_user_identity" not in content:
                violations.append(Violation(
                    file_path=file_path,
                    line_number=1,
                    pattern_name="unused_identity_utils",
                    matched_text="(identity_utils imported but not used)",
                    severity=Severity.MEDIUM,
                    fix_suggestion="Use extract_user_identity(context, payload) in agent_invocation",
                ))

    return violations


def scan_directory(directory: str, extensions: List[str] = None) -> List[Violation]:
    """Scan a directory recursively for violations."""
    if extensions is None:
        extensions = [".py"]

    all_violations = []
    directory = Path(directory)

    # Directories to skip
    skip_dirs = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", "coverage", ".pytest_cache",
    }

    for file_path in directory.rglob("*"):
        # Skip directories in skip_dirs
        if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
            continue

        # Only process files with matching extensions
        if file_path.suffix not in extensions:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            violations = scan_file(str(file_path), content)
            all_violations.extend(violations)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)

    return all_violations


def print_report(violations: List[Violation], show_fix: bool = False, show_info: bool = False) -> dict:
    """Print a formatted report of violations."""
    # Filter out INFO level unless requested
    if not show_info:
        violations = [v for v in violations if v.severity != Severity.INFO]

    # Group by severity
    by_severity = {}
    for v in violations:
        by_severity.setdefault(v.severity, []).append(v)

    # Calculate stats
    critical_count = len(by_severity.get(Severity.CRITICAL, []))
    high_count = len(by_severity.get(Severity.HIGH, []))
    actionable_count = critical_count + high_count

    if not violations:
        print("\n" + "=" * 70)
        print(" AgentCore Identity Compliance: PASSED ")
        print("=" * 70)
        print("\nNo actionable violations found.")
        if not show_info:
            print("(Run with --verbose to see INFO-level pass-through patterns)")
        return {"passed": True, "critical": 0, "high": 0, "total": 0}

    print("\n" + "=" * 70)
    print(" AgentCore Identity Compliance Report")
    print("=" * 70)

    # Summary
    print(f"\nTotal findings: {len(violations)}")
    for severity in Severity:
        count = len(by_severity.get(severity, []))
        if count:
            marker = "" if severity == Severity.INFO else ""
            print(f"  {severity.value}: {count} {marker}")

    # Status
    if actionable_count == 0:
        print("\n STATUS: COMPLIANT (no CRITICAL or HIGH violations)")
    else:
        print(f"\n STATUS: NON-COMPLIANT ({actionable_count} actionable violations)")

    # Details
    for severity in Severity:
        violations_for_severity = by_severity.get(severity, [])
        if not violations_for_severity:
            continue

        print(f"\n{'─' * 70}")
        print(f" {severity.value} Findings")
        print(f"{'─' * 70}")

        for v in violations_for_severity:
            print(f"\n  File: {v.file_path}:{v.line_number}")
            print(f"  Pattern: {v.pattern_name}")
            print(f"  Matched: {v.matched_text}")
            if show_fix and v.fix_suggestion:
                print(f"  Fix: {v.fix_suggestion}")

    print("\n" + "=" * 70)

    return {
        "passed": actionable_count == 0,
        "critical": critical_count,
        "high": high_count,
        "total": len(violations),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Scan codebase for AgentCore Identity compliance violations"
    )
    parser.add_argument(
        "--directory", "-d",
        default="server/agentcore-inventory",
        help="Directory to scan (default: server/agentcore-inventory)"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Show fix suggestions for each violation"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any CRITICAL or HIGH violations found"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show INFO-level findings (pass-through patterns)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Scan directory
    print(f"Scanning {args.directory} for AgentCore Identity compliance...")
    violations = scan_directory(args.directory)

    if args.json:
        import json
        output = [
            {
                "file": v.file_path,
                "line": v.line_number,
                "pattern": v.pattern_name,
                "matched": v.matched_text,
                "severity": v.severity.value,
                "fix": v.fix_suggestion,
            }
            for v in violations
        ]
        print(json.dumps(output, indent=2))
        sys.exit(0)

    result = print_report(violations, show_fix=args.fix, show_info=args.verbose)

    # Exit code
    if args.strict and not result["passed"]:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
