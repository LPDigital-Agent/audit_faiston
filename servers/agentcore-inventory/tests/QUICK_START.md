# Quick Start - Agent Room Service Tests

## Installation

```bash
cd /Users/fabio.santos/LPD\ Repos/lpd-faiston-allinone/server/agentcore-inventory
pip install -r requirements-test.txt
```

## Run All Tests

```bash
make test
# or
./run_tests.sh
# or
pytest tests/test_agent_room_service.py -v
```

## Run Specific Tests

```bash
# Test a specific function
pytest tests/test_agent_room_service.py::TestGetAgentProfiles -v

# Test a specific case
pytest tests/test_agent_room_service.py::TestGetAgentProfiles::test_returns_all_primary_agents -v

# Test by pattern
pytest tests/test_agent_room_service.py -k "agent_profiles" -v
```

## With Coverage

```bash
make test-cov
# or
pytest tests/test_agent_room_service.py --cov=tools --cov-report=html
# Open htmlcov/index.html to view report
```

## Test Markers

```bash
# Unit tests only
pytest tests/test_agent_room_service.py -m unit -v

# Integration tests only
pytest tests/test_agent_room_service.py -m integration -v
```

## Common Commands

```bash
# Help
make help

# Clean artifacts
make clean

# Verbose output
make test-verbose

# Run specific file
make test-file FILE=test_agent_room_service.py

# Run specific test case
make test-case CASE="test_returns_all_primary_agents"
```

## Test Structure

```
tests/
├── __init__.py                      # Package init
├── conftest.py                      # Fixtures and config
├── test_agent_room_service.py       # Main test suite (56 tests)
├── README.md                        # Detailed documentation
├── TEST_SUMMARY.md                  # Test results and metrics
└── QUICK_START.md                   # This file
```

## Test Results

Total Tests: 56
Passed: 56 (100%)
Failed: 0
Execution Time: ~0.08s

## What's Tested

✓ Agent Profiles (8 tests)
✓ Recent Events (7 tests)
✓ Learning Stories (2 tests)
✓ Active Workflow (2 tests)
✓ Pending Decisions (6 tests)
✓ HIL Questions (8 tests)
✓ HIL Options (5 tests)
✓ Event Emission (4 tests)
✓ Data Aggregation (4 tests)
✓ Helper Functions (2 tests)
✓ Integration Flows (2 tests)
✓ Edge Cases (6 tests)

## Files Created

- `pytest.ini` - Pytest configuration
- `requirements-test.txt` - Test dependencies
- `run_tests.sh` - Test runner script
- `Makefile` - Make commands
- `tests/` - Test directory with all test files

## Need Help?

See `tests/README.md` for detailed documentation.
