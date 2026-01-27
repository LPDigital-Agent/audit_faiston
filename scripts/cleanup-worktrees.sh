#!/usr/bin/env bash
# cleanup-worktrees.sh - Remove worktrees for merged branches
#
# Usage:
#   ./scripts/cleanup-worktrees.sh [--dry-run]
#
# Removes worktrees where the branch has been merged to main
#
# Exit codes:
#   0 = Success
#   1 = Error
#
set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="true"
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
MAIN_BRANCH="main"

echo "Scanning for stale worktrees..."
echo ""

# Fetch latest
git fetch origin "$MAIN_BRANCH" --quiet

# Get merged branches
MERGED_BRANCHES=$(git branch --merged "origin/$MAIN_BRANCH" | sed 's/^\*//;s/^ *//' | grep -v "^$MAIN_BRANCH$" || true)

# Process each worktree
REMOVED=0
while IFS= read -r line; do
    [[ -z "$line" ]] && continue

    worktree_path=$(echo "$line" | awk '{print $1}')
    branch_info=$(echo "$line" | awk '{print $2}' | tr -d '[]')

    # Skip main worktree
    if [[ "$worktree_path" == "$REPO_ROOT" ]]; then
        continue
    fi

    # Skip if no branch info
    if [[ -z "$branch_info" ]]; then
        continue
    fi

    # Check if branch is merged
    if echo "$MERGED_BRANCHES" | grep -q "^$branch_info$"; then
        if [[ -n "$DRY_RUN" ]]; then
            echo "[DRY RUN] Would remove: $worktree_path ($branch_info)"
        else
            echo "Removing: $worktree_path ($branch_info)"
            git worktree remove "$worktree_path" --force 2>/dev/null || true
            git branch -d "$branch_info" 2>/dev/null || true
            ((REMOVED++)) || true
        fi
    fi
done < <(git worktree list)

echo ""
if [[ -n "$DRY_RUN" ]]; then
    echo "Run without --dry-run to actually remove worktrees"
else
    echo "Removed $REMOVED stale worktree(s)"
fi

# Prune stale worktree references
echo ""
echo "Pruning stale worktree references..."
git worktree prune

# Show remaining worktrees
echo ""
echo "Current worktrees:"
git worktree list
