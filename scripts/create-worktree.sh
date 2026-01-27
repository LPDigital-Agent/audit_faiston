#!/usr/bin/env bash
# create-worktree.sh - Create a new worktree with branch
#
# Usage:
#   ./scripts/create-worktree.sh <branch-name> [base-branch]
#
# Creates worktree at: ../lpd-faiston-agent-cockpit-<branch-name>
#
# Exit codes:
#   0 = Success
#   1 = Error (missing args, worktree exists, etc.)
#
set -euo pipefail

# Arguments
BRANCH_NAME=${1:-}
BASE_BRANCH=${2:-main}

# Validation
if [[ -z "$BRANCH_NAME" ]]; then
    echo "Usage: $0 <branch-name> [base-branch]"
    echo "Example: $0 feat-dark-mode"
    echo "         $0 fix-auth-bug release/v2"
    exit 1
fi

# Add fabio/ prefix if not present
if [[ ! "$BRANCH_NAME" =~ ^fabio/ ]]; then
    BRANCH_NAME="fabio/$BRANCH_NAME"
fi

# Paths
REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_NAME=$(basename "$REPO_ROOT")
WORKTREE_DIR=$(dirname "$REPO_ROOT")
WORKTREE_NAME="${REPO_NAME}-${BRANCH_NAME//\//-}"  # Replace / with -
WORKTREE_PATH="${WORKTREE_DIR}/${WORKTREE_NAME}"

# Check if worktree already exists
if git worktree list | grep -q "$WORKTREE_PATH"; then
    echo "ERROR: Worktree already exists at $WORKTREE_PATH"
    echo "To remove: git worktree remove $WORKTREE_PATH"
    exit 1
fi

# Check if branch already exists
if git rev-parse --verify "$BRANCH_NAME" >/dev/null 2>&1; then
    echo "Branch $BRANCH_NAME already exists, creating worktree without -b flag..."
    git fetch origin "$BASE_BRANCH" 2>/dev/null || true
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    # Create worktree with new branch
    echo "Creating worktree: $WORKTREE_PATH"
    echo "Branch: $BRANCH_NAME (from $BASE_BRANCH)"

    git fetch origin "$BASE_BRANCH" 2>/dev/null || true
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "origin/$BASE_BRANCH"
fi

# Setup environment (install dependencies)
cd "$WORKTREE_PATH"
if [[ -f "pnpm-lock.yaml" ]]; then
    echo "Installing dependencies with pnpm..."
    pnpm install --frozen-lockfile
fi

# Create TASK.md for context
cat > "$WORKTREE_PATH/TASK.md" << EOF
# Task: ${BRANCH_NAME#fabio/}

## Description
[Add your task description here]

## Files to Modify
-

## Success Criteria
- [ ]

## Created
- Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- Worktree: $WORKTREE_PATH
- Base: $BASE_BRANCH
EOF

echo ""
echo "✅ Worktree created successfully!"
echo "   Path: $WORKTREE_PATH"
echo "   Branch: $BRANCH_NAME"
echo ""
echo "To start working:"
echo "   cd $WORKTREE_PATH"
echo "   code ."
echo ""
echo "To remove when done:"
echo "   git worktree remove $WORKTREE_PATH"
