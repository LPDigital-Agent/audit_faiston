"""Pytest configuration and fixtures for AgentCore tests."""
# =============================================================================
# CRITICAL: Module-level mocks MUST be set BEFORE any imports
# =============================================================================
# This mock MUST be at the top of the file, before pytest imports any test modules.
# When pytest collects tests, it imports test files which import production modules.
# The inventory_hub/main.py has a top-level import:
#   from bedrock_agentcore.runtime import BedrockAgentCoreApp
# This import runs BEFORE any fixture can mock it. CI only installs requirements-test.txt
# which doesn't include bedrock-agentcore, causing ModuleNotFoundError.
# By mocking sys.modules at file-level, Python's import machinery finds our mock.
# =============================================================================
import sys
from unittest.mock import MagicMock

# Mock bedrock_agentcore before any imports (CI doesn't install this package)
_mock_agentcore = MagicMock()
_mock_agentcore.runtime = MagicMock()
_mock_agentcore.runtime.BedrockAgentCoreApp = MagicMock()
sys.modules['bedrock_agentcore'] = _mock_agentcore
sys.modules['bedrock_agentcore.runtime'] = _mock_agentcore.runtime

# =============================================================================
# Mock strands SDK before any imports (CI doesn't install strands-agents)
# =============================================================================
# Required imports in production code:
#   - from strands import Agent, tool
#   - from strands.models.gemini import GeminiModel
#   - from strands.multiagent.a2a import A2AServer
#   - from strands.tools import tool
#   - from strands_tools.a2a_client import A2AClientToolProvider
#   - from strands.hooks import HookProvider, HookRegistry
#   - from strands.hooks.events import AfterInvocationEvent
#
# IMPORTANT: HookProvider and HookRegistry must be real classes (not MagicMock)
# because production code inherits from HookProvider. MagicMock inheritance breaks
# with AttributeError: _mock_methods. Use stub classes instead.
# =============================================================================


class _StubHookProvider:
    """Stub for strands.hooks.HookProvider - allows inheritance without MagicMock issues."""

    def register_hooks(self, registry):
        """Override in subclasses to register event callbacks."""
        pass


class _StubHookRegistry:
    """Stub for strands.hooks.HookRegistry."""

    def add_callback(self, event_type, callback):
        """Register callback for event type."""
        pass


class AfterInvocationEvent:
    """Stub for strands.hooks.events.AfterInvocationEvent."""

    pass


_mock_strands = MagicMock()
_mock_strands.Agent = MagicMock()
_mock_strands.tool = MagicMock(side_effect=lambda func: func)  # Pass-through decorator
sys.modules['strands'] = _mock_strands
sys.modules['strands.agent'] = MagicMock()
sys.modules['strands.models'] = MagicMock()
sys.modules['strands.models.gemini'] = MagicMock()
sys.modules['strands.multiagent'] = MagicMock()
sys.modules['strands.multiagent.a2a'] = MagicMock()
sys.modules['strands.tools'] = MagicMock()

# Use stub classes for hooks (production code inherits from HookProvider)
_mock_strands_hooks = MagicMock()
_mock_strands_hooks.HookProvider = _StubHookProvider
_mock_strands_hooks.HookRegistry = _StubHookRegistry
_mock_strands_hooks.events = MagicMock()
_mock_strands_hooks.events.AfterInvocationEvent = AfterInvocationEvent
sys.modules['strands.hooks'] = _mock_strands_hooks
sys.modules['strands.hooks.events'] = _mock_strands_hooks.events

sys.modules['strands_tools'] = MagicMock()
sys.modules['strands_tools.a2a_client'] = MagicMock()

# Mock google.genai SDK before any imports (CI doesn't install google-genai)
# Required imports in production code:
#   - from google.genai import types as genai_types
#   - from google.genai import Client
_mock_google = MagicMock()
_mock_google.genai = MagicMock()
_mock_google.genai.types = MagicMock()
sys.modules['google'] = _mock_google
sys.modules['google.genai'] = _mock_google.genai

# Mock a2a SDK before any imports (CI doesn't install a2a)
# Required imports in production code:
#   - from a2a.types import AgentSkill
#   - from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
#   - from a2a.types import Message, Part, Role, TextPart
# NOTE: AgentSkill must return instances with unique IDs for test_agent_cards.py
import uuid


class MockAgentSkill:
    """Mock AgentSkill that creates instances with unique IDs."""

    def __init__(self, id=None, name=None, description=None, **kwargs):
        self.id = id or f"skill_{uuid.uuid4().hex[:8]}"
        self.name = name or "MockSkill"
        self.description = description or "A mock skill description for testing purposes"
        # Store any additional kwargs as attributes
        for key, value in kwargs.items():
            setattr(self, key, value)


_mock_a2a = MagicMock()
# a2a.client module (Strands Framework A2A Protocol)
_mock_a2a.client = MagicMock()
_mock_a2a.client.A2ACardResolver = MagicMock()
_mock_a2a.client.ClientConfig = MagicMock()
_mock_a2a.client.ClientFactory = MagicMock()
# a2a.types module - preserve MockAgentSkill for test_agent_cards.py
_mock_a2a.types = MagicMock()
_mock_a2a.types.AgentSkill = MockAgentSkill
_mock_a2a.types.Message = MagicMock()
_mock_a2a.types.Part = MagicMock()
_mock_a2a.types.Role = MagicMock()
_mock_a2a.types.TextPart = MagicMock()
sys.modules['a2a'] = _mock_a2a
sys.modules['a2a.client'] = _mock_a2a.client
sys.modules['a2a.types'] = _mock_a2a.types

# Mock boto3 and botocore before any imports (CI doesn't install these)
# Required imports in production code:
#   - tools/library/file_processing.py: import boto3
#   - tools/library/file_processing.py: from botocore.config import Config
#   - tools/library/file_processing.py: from botocore.exceptions import ClientError
#   - Used for S3 operations in file analysis tools
_mock_boto3 = MagicMock()
_mock_boto3.client = MagicMock(return_value=MagicMock())
_mock_boto3.resource = MagicMock(return_value=MagicMock())
_mock_boto3.Session = MagicMock(return_value=MagicMock())
sys.modules['boto3'] = _mock_boto3


# botocore.exceptions.ClientError must be a real exception class for except clauses
class MockClientError(Exception):
    """Mock ClientError that inherits from Exception for proper exception handling."""

    def __init__(self, error_response=None, operation_name=None):
        self.response = error_response or {"Error": {"Code": "MockError", "Message": "Mock error"}}
        self.operation_name = operation_name or "MockOperation"
        super().__init__(f"An error occurred ({self.response['Error']['Code']})")


_mock_botocore = MagicMock()
_mock_botocore.config = MagicMock()
_mock_botocore.config.Config = MagicMock()
_mock_botocore.exceptions = MagicMock()
_mock_botocore.exceptions.ClientError = MockClientError
_mock_botocore.auth = MagicMock()
_mock_botocore.auth.SigV4Auth = MagicMock()
_mock_botocore.awsrequest = MagicMock()
_mock_botocore.awsrequest.AWSRequest = MagicMock()
_mock_botocore.session = MagicMock()
_mock_botocore.session.Session = MagicMock()
sys.modules['botocore'] = _mock_botocore
sys.modules['botocore.config'] = _mock_botocore.config
sys.modules['botocore.exceptions'] = _mock_botocore.exceptions
sys.modules['botocore.auth'] = _mock_botocore.auth
sys.modules['botocore.awsrequest'] = _mock_botocore.awsrequest
sys.modules['botocore.session'] = _mock_botocore.session

# NOTE: a2a module (Strands Framework A2A Protocol) is mocked above at line ~96
# with consolidated MockAgentSkill support. Do not duplicate the mock here.

# =============================================================================
# Environment variables MUST be set BEFORE any imports
# =============================================================================
# agents/utils.py has module-level get_required_env() calls that run at import time.
# These must be set before pytest imports test modules.
import os
os.environ.setdefault("INVENTORY_TABLE", "test-inventory-table")
os.environ.setdefault("HIL_TASKS_TABLE", "test-hil-tasks-table")
os.environ.setdefault("AUDIT_LOG_TABLE", "test-audit-log-table")
os.environ.setdefault("DOCUMENTS_BUCKET", "test-documents-bucket")

# =============================================================================
# Standard imports (AFTER module-level mocks and env vars)
# =============================================================================
import pytest
from unittest.mock import patch  # MagicMock already imported above
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
