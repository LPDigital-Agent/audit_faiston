# AgentCore Inventory Tests

Comprehensive test suite for the AgentCore Inventory service.

## Setup

Install test dependencies:

```bash
cd /Users/fabio.santos/LPD\ Repos/lpd-faiston-allinone/server/agentcore-inventory
pip install -r requirements-test.txt
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=tools --cov=agents --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_agent_room_service.py
```

### Run specific test class
```bash
pytest tests/test_agent_room_service.py::TestGetAgentProfiles
```

### Run specific test
```bash
pytest tests/test_agent_room_service.py::TestGetAgentProfiles::test_returns_all_primary_agents
```

### Run with verbose output
```bash
pytest -v
```

### Run only unit tests
```bash
pytest -m unit
```

### Run only integration tests
```bash
pytest -m integration
```

## Test Organization

### `conftest.py`
- Global fixtures and configuration
- Mock objects (DynamoDB, audit logger)
- Sample data fixtures
- Environment reset

### `test_agent_room_service.py`
Comprehensive tests for Agent Room Service:

#### Test Classes
- `TestGetAgentProfiles` - Agent profile retrieval
- `TestGetRecentEvents` - Live feed event retrieval
- `TestGetLearningStories` - Learning stories (TODO)
- `TestGetActiveWorkflow` - Active workflow (TODO)
- `TestGetPendingDecisions` - HIL task retrieval
- `TestHumanizeHilQuestion` - HIL question formatting
- `TestGetHilOptions` - HIL option generation
- `TestEmitAgentEvent` - Event emission
- `TestGetAgentRoomData` - Main aggregation function
- `TestGetAuditTable` - Helper function
- `TestAgentRoomServiceIntegration` - Integration tests
- `TestEdgeCases` - Edge cases and error handling

#### Coverage
- All public functions tested
- Edge cases covered
- Error handling verified
- Integration scenarios tested

## Writing New Tests

### Test Structure
```python
class TestMyFeature:
    """Test description."""

    def test_basic_functionality(self):
        """Should do the basic thing."""
        result = my_function()
        assert result == expected

    @patch('module.Dependency')
    def test_with_mock(self, mock_dep):
        """Should work with mocked dependency."""
        mock_dep.return_value = "mocked"
        result = my_function()
        assert result == "expected"
```

### Fixture Usage
```python
def test_with_fixture(mock_dynamodb_client):
    """Should use fixture."""
    mock_dynamodb_client.query_pk.return_value = []
    result = my_function(db_client=mock_dynamodb_client)
    assert result is not None
```

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, multiple components)
- `@pytest.mark.slow` - Slow running tests

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Push to main branch
- Pre-deployment validation

## Coverage Goals

- Line coverage: 80%+
- Branch coverage: 75%+
- Function coverage: 90%+

## Common Issues

### Import errors
Make sure the parent directory is in PYTHONPATH:
```bash
export PYTHONPATH=/Users/fabio.santos/LPD\ Repos/lpd-faiston-allinone/server/agentcore-inventory:$PYTHONPATH
```

### Mock not working
Mock at the point of import, not at definition:
```python
# Correct
@patch('tools.agent_room_service.SGADynamoDBClient')

# Incorrect
@patch('tools.dynamodb_client.SGADynamoDBClient')
```

### Fixture not found
Check that conftest.py is in the correct location and properly named.
