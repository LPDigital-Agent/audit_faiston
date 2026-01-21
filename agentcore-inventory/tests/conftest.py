"""Pytest configuration and fixtures for AgentCore tests."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# =============================================================================
# X-Ray Tracer Mock (auto-use to prevent failures in test environment)
# =============================================================================

@pytest.fixture(autouse=True)
def mock_xray_tracer():
    """
    Mock X-Ray tracer to prevent failures when SDK is installed but no segment exists.

    The X-Ray decorators (@trace_memory_operation, @trace_tool_call) fail in tests
    because there's no active X-Ray segment. This fixture mocks the module-level
    recorder to use NoOp implementations.
    """
    class MockSubsegment:
        def put_annotation(self, key, value):
            pass

        def put_metadata(self, key, value, namespace="default"):
            pass

        def add_exception(self, exception, stack=None):
            pass

    class MockContext:
        def __enter__(self):
            return MockSubsegment()

        def __exit__(self, *args):
            pass

    class MockRecorder:
        def in_subsegment(self, name):
            return MockContext()

        def begin_subsegment(self, name):
            return MockSubsegment()

        def end_subsegment(self):
            pass

        def put_annotation(self, key, value):
            pass

        def put_metadata(self, key, value, namespace="default"):
            pass

    # Patch the xray_tracer module to use our mock recorder
    with patch("shared.xray_tracer._get_xray_recorder", return_value=MockRecorder()):
        yield


@pytest.fixture
def mock_dynamodb_client():
    """Mock DynamoDB client for testing."""
    client = MagicMock()
    client.query_pk.return_value = []
    client.query_gsi.return_value = []
    return client


@pytest.fixture
def mock_audit_logger():
    """Mock SGAAuditLogger for testing."""
    logger = MagicMock()
    logger.log_event.return_value = True
    return logger


@pytest.fixture
def sample_audit_event():
    """Sample audit event for testing."""
    return {
        "event_id": "evt_123",
        "PK": "LOG#2026-01-11",
        "SK": "EVT#2026-01-11T10:30:00.000Z#evt_123",
        "timestamp": "2026-01-11T10:30:00.000Z",
        "event_type": "AGENT_ACTIVITY",
        "actor_type": "AGENT",
        "actor_id": "nexo_import",
        "entity_type": "agent_status",
        "entity_id": "nexo_import",
        "action": "trabalhando",
        "details": {
            "agent_id": "nexo_import",
            "status": "trabalhando",
            "message": "Analisando arquivo CSV com 1,658 linhas...",
        },
    }


@pytest.fixture
def sample_hil_task():
    """Sample HIL task for testing."""
    return {
        "task_id": "task_123",
        "PK": "TASK#task_123",
        "SK": "METADATA",
        "GSI1PK": "USER#user_123",
        "GSI1SK": "TASK#PENDING#2026-01-11T10:30:00.000Z",
        "task_type": "confirm_nf_entry",
        "priority": "high",
        "created_at": "2026-01-11T10:30:00.000Z",
        "entity_id": "nf_456",
        "details": {
            "count": 25,
            "nf_number": "123456",
        },
    }


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent timestamps."""
    mock_dt = MagicMock()
    mock_dt.utcnow.return_value = datetime(2026, 1, 11, 10, 30, 0)
    return mock_dt


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test."""
    import os
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)
