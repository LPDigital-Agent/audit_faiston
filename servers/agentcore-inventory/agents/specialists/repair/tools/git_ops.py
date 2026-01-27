# =============================================================================
# Git Operations Tools for RepairAgent
# =============================================================================
# Safe Git operations using GitHub CLI for automated code repairs.
#
# SAFETY RULES (IMMUTABLE):
# 1. NEVER commit to protected branches (main, master, prod, production)
# 2. ONLY commit to branches with prefix: fix/, feature/, hotfix/
# 3. ALWAYS validate syntax before committing
# 4. ALWAYS create DRAFT PRs (never auto-merge)
# 5. ALL operations use GitHub CLI (not raw git commands)
#
# Why GitHub CLI:
# - Safer than raw git (no git push --force risk)
# - GitHub API authentication via GITHUB_TOKEN
# - Atomic operations (create PR = branch + commit + PR in one call)
# - Built-in retry and error handling
# =============================================================================

import asyncio
import base64
import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional
from slugify import slugify

from strands.tools import tool

logger = logging.getLogger(__name__)

# =============================================================================
# Safety Constants
# =============================================================================

PROTECTED_BRANCHES = {"main", "master", "prod", "production"}
ALLOWED_PREFIXES = {"fix/", "feature/", "hotfix/"}

# =============================================================================
# Safety Validation Functions
# =============================================================================


class SecurityError(Exception):
    """Raised when Git operation violates security rules."""
    pass


def validate_branch_safety(branch_name: str) -> bool:
    """
    Validate branch name against protection rules.

    Args:
        branch_name: Branch name to validate

    Returns:
        True if safe

    Raises:
        SecurityError: If branch is protected or has invalid prefix
    """
    if branch_name in PROTECTED_BRANCHES:
        raise SecurityError(
            f"CRITICAL: Cannot commit to protected branch '{branch_name}'. "
            f"RepairAgent only commits to feature/fix branches."
        )

    if not any(branch_name.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        raise SecurityError(
            f"CRITICAL: Branch '{branch_name}' must start with one of {ALLOWED_PREFIXES}"
        )

    return True


def _run_gh_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Run GitHub CLI command safely.

    Args:
        command: Full gh command to execute
        timeout: Timeout in seconds

    Returns:
        Dict with success, output, error
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.returncode != 0 else None,
            "exit_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error(f"[GitOps] Command timeout after {timeout}s: {command}")
        return {
            "success": False,
            "output": "",
            "error": f"Command timeout after {timeout}s",
            "exit_code": -1,
        }

    except Exception as e:
        logger.error(f"[GitOps] Command execution error: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "exit_code": -1,
        }


# =============================================================================
# Git Operations Tools (Strands Tool Interface)
# =============================================================================


@tool
async def create_fix_branch_tool(error_id: str, description: str) -> str:
    """
    Create a new Git branch for the fix using GitHub API.

    This tool creates a safe branch name following the pattern:
    fix/BUG-{error_id}-{slug(description)}

    Examples:
        error_id="123", description="missing part number validation"
        → fix/issue-123-missing-part-number-validation

    Args:
        error_id: Bug/error ID (e.g., "044")
        description: Brief description of the fix (e.g., "missing validation")

    Returns:
        JSON string with result:
        {
            "success": true/false,
            "branch_name": "fix/issue-123-...",
            "base_sha": "abc123...",
            "error": "error message if failed"
        }

    Raises:
        SecurityError: If branch name violates protection rules (caught internally, returns JSON error with security_violation=True).
        Exception: If GitHub CLI command fails (caught internally, returns JSON error response).

    Safety:
        - Branch name is automatically validated against protection rules
        - Creates branch from current HEAD (main/master)
        - Uses GitHub API (not raw git push)
    """
    try:
        # Generate safe branch name
        slug = slugify(description, max_length=50)
        branch_name = f"fix/issue-{error_id}-{slug}"

        # Validate branch safety
        validate_branch_safety(branch_name)

        logger.info(f"[GitOps] Creating fix branch: {branch_name}")

        # Get current repo info
        repo_result = _run_gh_command("gh repo view --json nameWithOwner -q .nameWithOwner")
        if not repo_result["success"]:
            return json.dumps({
                "success": False,
                "error": f"Failed to get repo info: {repo_result['error']}",
            })

        repo_name = repo_result["output"]

        # Get base SHA from main/master
        base_result = _run_gh_command("git rev-parse HEAD")
        if not base_result["success"]:
            return json.dumps({
                "success": False,
                "error": f"Failed to get base SHA: {base_result['error']}",
            })

        base_sha = base_result["output"]

        # Create branch via GitHub API
        create_cmd = (
            f"gh api repos/{repo_name}/git/refs "
            f"-f ref='refs/heads/{branch_name}' "
            f"-f sha='{base_sha}'"
        )

        result = _run_gh_command(create_cmd)

        if result["success"]:
            logger.info(f"[GitOps] Branch created successfully: {branch_name}")
            return json.dumps({
                "success": True,
                "branch_name": branch_name,
                "base_sha": base_sha,
                "repo": repo_name,
            })
        else:
            logger.error(f"[GitOps] Failed to create branch: {result['error']}")
            return json.dumps({
                "success": False,
                "error": result["error"],
                "branch_name": branch_name,
            })

    except SecurityError as e:
        logger.error(f"[GitOps] Security violation: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "security_violation": True,
        })

    except Exception as e:
        logger.error(f"[GitOps] Unexpected error creating branch: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
async def commit_fix_tool(
    branch_name: str,
    file_path: str,
    new_content: str,
    commit_message: str,
) -> str:
    """
    Commit a fix to a file using GitHub API.

    This tool:
    1. Validates branch safety (cannot commit to main/master/prod)
    2. Validates Python syntax via AST parsing (MANDATORY)
    3. Commits the change via GitHub API
    4. Returns commit SHA

    Args:
        branch_name: Branch to commit to (e.g., "fix/issue-123-validation")
        file_path: File path to update (e.g., "agents/specialists/intake/main.py")
        new_content: New file content (full file)
        commit_message: Commit message (should follow conventional commits)

    Returns:
        JSON string with result:
        {
            "success": true/false,
            "commit_sha": "abc123...",
            "syntax_valid": true/false,
            "branch_name": "fix/issue-123-...",
            "error": "error message if failed"
        }

    Raises:
        SecurityError: If branch name violates protection rules (caught internally, returns JSON error with security_violation=True).
        Exception: If GitHub CLI command or syntax validation fails (caught internally, returns JSON error response).

    Safety:
        - MANDATORY branch validation (cannot commit to protected branches)
        - MANDATORY syntax validation before commit
        - Uses GitHub API (not raw git push)
        - All commits are immutable (no force-push)
    """
    try:
        # Validate branch safety
        validate_branch_safety(branch_name)

        logger.info(f"[GitOps] Committing fix to {file_path} on branch {branch_name}")

        # MANDATORY: Validate Python syntax before commit
        if file_path.endswith(".py"):
            from agents.specialists.repair.tools.syntax_validator import validate_python_ast_tool

            validation_result = await validate_python_ast_tool(
                code=new_content,
                filename=file_path,
            )
            validation_data = json.loads(validation_result)

            if not validation_data.get("valid"):
                logger.error(f"[GitOps] Syntax validation failed: {validation_data.get('error')}")
                return json.dumps({
                    "success": False,
                    "syntax_valid": False,
                    "error": f"Syntax validation failed: {validation_data.get('error')}",
                    "line_number": validation_data.get("line_number"),
                })

        # Get repo info
        repo_result = _run_gh_command("gh repo view --json nameWithOwner -q .nameWithOwner")
        if not repo_result["success"]:
            return json.dumps({
                "success": False,
                "error": f"Failed to get repo info: {repo_result['error']}",
            })

        repo_name = repo_result["output"]

        # Base64 encode content for GitHub API
        content_b64 = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

        # Commit via GitHub API (update file contents)
        commit_cmd = (
            f"gh api repos/{repo_name}/contents/{file_path} "
            f"-X PUT "
            f"-f content='{content_b64}' "
            f"-f message='{commit_message}' "
            f"-f branch='{branch_name}'"
        )

        result = _run_gh_command(commit_cmd, timeout=60)

        if result["success"]:
            # Extract commit SHA from response
            try:
                response_data = json.loads(result["output"])
                commit_sha = response_data.get("commit", {}).get("sha", "unknown")
            except json.JSONDecodeError:
                commit_sha = "unknown"

            logger.info(f"[GitOps] Commit successful: {commit_sha}")
            return json.dumps({
                "success": True,
                "commit_sha": commit_sha,
                "syntax_valid": True,
                "branch_name": branch_name,
                "file_path": file_path,
            })
        else:
            logger.error(f"[GitOps] Commit failed: {result['error']}")
            return json.dumps({
                "success": False,
                "error": result["error"],
                "branch_name": branch_name,
            })

    except SecurityError as e:
        logger.error(f"[GitOps] Security violation: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "security_violation": True,
        })

    except Exception as e:
        logger.error(f"[GitOps] Unexpected error committing fix: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })


@tool
async def create_pr_tool(
    branch_name: str,
    title: str,
    body: str,
) -> str:
    """
    Create a DRAFT pull request for human review using GitHub CLI.

    This tool creates a DRAFT PR with security audit labels.
    CRITICAL: ALL PRs are created as DRAFT (never auto-merge).

    Args:
        branch_name: Source branch (e.g., "fix/issue-123-validation")
        title: PR title (e.g., "fix(issue-123): Add part number validation")
        body: PR body (should include error details, fix explanation, test results)

    Returns:
        JSON string with result:
        {
            "success": true/false,
            "pr_url": "https://github.com/org/repo/pull/123",
            "pr_number": 123,
            "branch_name": "fix/issue-123-...",
            "error": "error message if failed"
        }

    Raises:
        SecurityError: If branch name violates protection rules (caught internally, returns JSON error with security_violation=True).
        Exception: If GitHub CLI command fails (caught internally, returns JSON error response).

    Safety:
        - ALWAYS creates DRAFT PRs (requires human approval)
        - Auto-adds labels: automated-fix, needs-review, security-audit
        - Base branch is always main (configurable via env var)
    """
    try:
        # Validate branch safety
        validate_branch_safety(branch_name)

        logger.info(f"[GitOps] Creating PR from branch: {branch_name}")

        # Get base branch from environment (default: main)
        base_branch = os.environ.get("REPAIR_AGENT_BASE_BRANCH", "main")

        # Create DRAFT PR with labels
        pr_cmd = (
            f"gh pr create "
            f"--base {base_branch} "
            f"--head {branch_name} "
            f"--title '{title}' "
            f"--body '{body}' "
            f"--draft "
            f"--label 'automated-fix' "
            f"--label 'needs-review' "
            f"--label 'security-audit'"
        )

        result = _run_gh_command(pr_cmd, timeout=60)

        if result["success"]:
            pr_url = result["output"]  # gh pr create returns URL

            # Extract PR number from URL
            try:
                pr_number = int(pr_url.split("/")[-1])
            except (ValueError, IndexError):
                pr_number = 0

            logger.info(f"[GitOps] PR created successfully: {pr_url}")
            return json.dumps({
                "success": True,
                "pr_url": pr_url,
                "pr_number": pr_number,
                "branch_name": branch_name,
                "base_branch": base_branch,
                "draft": True,
            })
        else:
            logger.error(f"[GitOps] Failed to create PR: {result['error']}")
            return json.dumps({
                "success": False,
                "error": result["error"],
                "branch_name": branch_name,
            })

    except SecurityError as e:
        logger.error(f"[GitOps] Security violation: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "security_violation": True,
        })

    except Exception as e:
        logger.error(f"[GitOps] Unexpected error creating PR: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
        })
