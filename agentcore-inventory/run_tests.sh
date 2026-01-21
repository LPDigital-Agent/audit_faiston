#!/bin/bash
# =============================================================================
# Test Runner for AgentCore Inventory Service
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Running AgentCore Inventory Tests${NC}"
echo -e "${GREEN}==============================================================================${NC}"

# Set PYTHONPATH
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Parse arguments
COVERAGE=false
VERBOSE=false
PATTERN=""
MARKERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -k)
            PATTERN="$2"
            shift 2
            ;;
        -m)
            MARKERS="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="python3 -m pytest"

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=tools --cov=agents --cov-report=term-missing --cov-report=html"
fi

if [ -n "$PATTERN" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $PATTERN"
fi

if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD -m $MARKERS"
fi

# Run tests
echo -e "${YELLOW}Running: $PYTEST_CMD${NC}"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}==============================================================================${NC}"
    echo -e "${GREEN}Tests PASSED${NC}"
    echo -e "${GREEN}==============================================================================${NC}"

    if [ "$COVERAGE" = true ]; then
        echo -e "${YELLOW}Coverage report generated at: htmlcov/index.html${NC}"
    fi

    exit 0
else
    echo ""
    echo -e "${RED}==============================================================================${NC}"
    echo -e "${RED}Tests FAILED${NC}"
    echo -e "${RED}==============================================================================${NC}"
    exit 1
fi
