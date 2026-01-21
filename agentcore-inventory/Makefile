# =============================================================================
# Makefile for AgentCore Inventory Service
# =============================================================================

.PHONY: help test test-cov test-unit test-integration test-verbose install-test clean

# Default target
help:
	@echo "AgentCore Inventory Service - Test Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make test              Run all tests"
	@echo "  make test-cov          Run tests with coverage report"
	@echo "  make test-unit         Run only unit tests"
	@echo "  make test-integration  Run only integration tests"
	@echo "  make test-verbose      Run tests with verbose output"
	@echo "  make install-test      Install test dependencies"
	@echo "  make clean             Clean test artifacts"
	@echo ""

# Install test dependencies
install-test:
	@echo "Installing test dependencies..."
	pip install -r requirements-test.txt

# Run all tests
test:
	@./run_tests.sh

# Run tests with coverage
test-cov:
	@./run_tests.sh --coverage

# Run only unit tests
test-unit:
	@./run_tests.sh -m unit

# Run only integration tests
test-integration:
	@./run_tests.sh -m integration

# Run tests with verbose output
test-verbose:
	@./run_tests.sh --verbose

# Run tests for specific file
test-file:
	@python3 -m pytest tests/$(FILE) -v

# Run specific test
test-case:
	@python3 -m pytest -k "$(CASE)" -v

# Clean test artifacts
clean:
	@echo "Cleaning test artifacts..."
	@rm -rf .pytest_cache
	@rm -rf htmlcov
	@rm -rf .coverage
	@rm -rf **/__pycache__
	@rm -rf **/*.pyc
	@echo "Clean complete!"
