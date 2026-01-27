#!/usr/bin/env bash
# list-worktrees.sh - List all worktrees with status
#
# Usage:
#   ./scripts/list-worktrees.sh
#
# Exit codes:
#   0 = Success
#
set -euo pipefail

REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")

echo "Git Worktrees for $REPO_NAME"
echo "============================================"
echo ""

# Fetch to get accurate ahead/behind counts
git fetch origin main --quiet 2>/dev/null || true

# Parse worktree list in porcelain format
current_path=""
current_head=""
current_branch=""

while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
        worktree\ *)
            current_path="${line#worktree }"
            ;;
        HEAD\ *)
            current_head="${line#HEAD }"
            ;;
        branch\ *)
            current_branch="${line#branch refs/heads/}"
            ;;
        "")
            # End of worktree entry, print info
            if [[ -n "$current_path" && -n "$current_branch" ]]; then
                # Get status info
                if [[ -d "$current_path" ]]; then
                    pushd "$current_path" >/dev/null 2>&1
                    changes=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
                    ahead=$(git rev-list --count "origin/main..HEAD" 2>/dev/null || echo "?")
                    behind=$(git rev-list --count "HEAD..origin/main" 2>/dev/null || echo "?")
                    popd >/dev/null 2>&1
                else
                    changes="?"
                    ahead="?"
                    behind="?"
                fi

                printf "📁 %-50s\n" "$current_path"
                printf "   └── Branch: %s\n" "$current_branch"
                printf "   └── Changes: %s | Ahead: %s | Behind: %s\n" "$changes" "$ahead" "$behind"
                echo ""
            fi
            # Reset for next entry
            current_path=""
            current_head=""
            current_branch=""
            ;;
    esac
done < <(git worktree list --porcelain; echo "")

echo "============================================"
echo "Commands:"
echo "  Create:  ./scripts/create-worktree.sh <name>"
echo "  Cleanup: ./scripts/cleanup-worktrees.sh [--dry-run]"
