#!/usr/bin/env bash
# sync-with-main.sh - Sync current branch with origin/main via rebase
#
# Exit codes:
#   0 = Success (synced or already up-to-date)
#   1 = Rebase conflict (manual resolution required)
#   2 = Error (not a git repo, uncommitted changes, fetch failed, etc.)
#   3 = On main branch (skip sync)
#
# Usage:
#   ./scripts/sync-with-main.sh [--quiet]
#
set -euo pipefail

QUIET=${1:-}
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Logging functions
log() { [[ "$QUIET" != "--quiet" ]] && echo "$1" || true; }
error() { echo "ERROR: $1" >&2; }

# Change to project directory
cd "$PROJECT_DIR" || { error "Cannot access project directory: $PROJECT_DIR"; exit 2; }

# =============================================================================
# VALIDATION
# =============================================================================

# Check if this is a git repository
git rev-parse --git-dir >/dev/null 2>&1 || { error "Not a git repository"; exit 2; }

# Get current branch
CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")
if [[ -z "$CURRENT_BRANCH" ]]; then
    error "Detached HEAD state - cannot sync"
    exit 2
fi

# Skip if on main branch
if [[ "$CURRENT_BRANCH" == "main" ]]; then
    log "On main branch - skipping sync"
    exit 3
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    error "Uncommitted changes detected - commit or stash first"
    exit 2
fi

# =============================================================================
# FETCH AND CHECK
# =============================================================================

log "Fetching origin/main..."
if ! git fetch origin main 2>/dev/null; then
    error "Failed to fetch origin/main - check network connection"
    exit 2
fi

# Get merge base and origin/main commit
MERGE_BASE=$(git merge-base HEAD origin/main 2>/dev/null || echo "")
ORIGIN_MAIN=$(git rev-parse origin/main 2>/dev/null || echo "")

if [[ -z "$MERGE_BASE" ]] || [[ -z "$ORIGIN_MAIN" ]]; then
    error "Cannot determine relationship with origin/main"
    exit 2
fi

# Check if already up-to-date
if [[ "$MERGE_BASE" == "$ORIGIN_MAIN" ]]; then
    log "Already up-to-date with origin/main"
    exit 0
fi

# =============================================================================
# REBASE
# =============================================================================

COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
log "Branch '$CURRENT_BRANCH' is $COMMITS_BEHIND commit(s) behind origin/main"
log "Rebasing onto origin/main..."

if git rebase origin/main; then
    log "Successfully rebased onto origin/main"
    exit 0
else
    error "Rebase conflict detected!"
    error "To resolve:"
    error "  1. Fix conflicts in the listed files"
    error "  2. git add <resolved-files>"
    error "  3. git rebase --continue"
    error ""
    error "Or abort with: git rebase --abort"
    exit 1
fi
