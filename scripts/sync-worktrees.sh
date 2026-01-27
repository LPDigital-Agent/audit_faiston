#!/usr/bin/env bash
# sync-worktrees.sh - Sync all worktrees with origin/main via rebase
#
# Usage:
#   ./scripts/sync-worktrees.sh [--dry-run]
#
# For each worktree (except main):
#   1. Checks for uncommitted changes
#   2. Fetches origin/main
#   3. Rebases onto origin/main
#
# Exit codes:
#   0 = All worktrees synced successfully
#   1 = Some worktrees had conflicts or errors
#
set -euo pipefail

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="true"
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_NAME=$(basename "$REPO_ROOT")
MAIN_BRANCH="main"

echo "Syncing all worktrees for $REPO_NAME"
echo "============================================"
echo ""

# Fetch main once from the current repo
echo "Fetching origin/main..."
git fetch origin "$MAIN_BRANCH" --quiet

# Track results
SYNCED=0
SKIPPED=0
FAILED=0
declare -a FAILED_WORKTREES=()

# Parse worktree list
current_path=""
current_branch=""

while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
        worktree\ *)
            current_path="${line#worktree }"
            ;;
        branch\ *)
            current_branch="${line#branch refs/heads/}"
            ;;
        "")
            # End of worktree entry, process it
            if [[ -n "$current_path" && -n "$current_branch" ]]; then
                # Skip main branch
                if [[ "$current_branch" == "$MAIN_BRANCH" ]]; then
                    echo "⏭️  Skipping: $current_branch (is main)"
                    ((SKIPPED++)) || true
                    current_path=""
                    current_branch=""
                    continue
                fi

                echo "📁 Processing: $current_path"
                echo "   Branch: $current_branch"

                if [[ -n "$DRY_RUN" ]]; then
                    echo "   [DRY RUN] Would rebase onto origin/main"
                    ((SYNCED++)) || true
                else
                    # Check for uncommitted changes
                    pushd "$current_path" >/dev/null 2>&1

                    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
                        echo "   ⚠️  SKIPPED: Uncommitted changes (commit or stash first)"
                        ((SKIPPED++)) || true
                        popd >/dev/null 2>&1
                        current_path=""
                        current_branch=""
                        continue
                    fi

                    # Check if already up-to-date
                    MERGE_BASE=$(git merge-base HEAD origin/main 2>/dev/null || echo "")
                    ORIGIN_MAIN=$(git rev-parse origin/main 2>/dev/null || echo "")

                    if [[ "$MERGE_BASE" == "$ORIGIN_MAIN" ]]; then
                        echo "   ✅ Already up-to-date"
                        ((SYNCED++)) || true
                        popd >/dev/null 2>&1
                        current_path=""
                        current_branch=""
                        continue
                    fi

                    # Count commits behind
                    BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
                    echo "   📥 $BEHIND commit(s) behind, rebasing..."

                    # Attempt rebase
                    if git rebase origin/main 2>/dev/null; then
                        echo "   ✅ Synced successfully"
                        ((SYNCED++)) || true
                    else
                        echo "   ❌ CONFLICT: Manual resolution required"
                        echo "      cd $current_path"
                        echo "      # Fix conflicts, then: git rebase --continue"
                        echo "      # Or abort: git rebase --abort"
                        git rebase --abort 2>/dev/null || true
                        FAILED_WORKTREES+=("$current_path")
                        ((FAILED++)) || true
                    fi

                    popd >/dev/null 2>&1
                fi
            fi
            # Reset for next entry
            current_path=""
            current_branch=""
            ;;
    esac
done < <(git worktree list --porcelain; echo "")

echo ""
echo "============================================"
echo "Summary:"
echo "  ✅ Synced:  $SYNCED"
echo "  ⏭️  Skipped: $SKIPPED"
echo "  ❌ Failed:  $FAILED"

if [[ $FAILED -gt 0 ]]; then
    echo ""
    echo "Failed worktrees (need manual resolution):"
    for wt in "${FAILED_WORKTREES[@]}"; do
        echo "  - $wt"
    done
    exit 1
fi

if [[ -n "$DRY_RUN" ]]; then
    echo ""
    echo "Run without --dry-run to actually sync worktrees"
fi

exit 0
