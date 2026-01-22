"""
Comprehensive tests for Agent Room Service.

Tests all public functions in tools/agent_room_service.py:
- get_agent_profiles()
- get_recent_events()
- get_learning_stories()
- get_active_workflow()
- get_pending_decisions()
- get_agent_room_data()
- emit_agent_event()
- _humanize_hil_question()
- _get_hil_options()
"""
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime

# Import module under test
from tools import agent_room_service


# =============================================================================
# Test get_agent_profiles()
# =============================================================================

class TestGetAgentProfiles:
    """Test get_agent_profiles function."""

    def test_returns_all_primary_agents(self):
        """Should return profiles for all 14 PRIMARY_AGENTS."""
        profiles = agent_room_service.get_agent_profiles()

        assert len(profiles) == 14
        assert all(isinstance(p, dict) for p in profiles)

    def test_profile_structure(self):
        """Should return profiles with correct structure."""
        profiles = agent_room_service.get_agent_profiles()

        required_fields = [
            "id", "technicalName", "friendlyName", "description",
            "avatar", "color", "status", "statusLabel", "lastActivity"
        ]

        for profile in profiles:
            for field in required_fields:
                assert field in profile, f"Missing field: {field}"

    def test_maps_technical_to_friendly_names(self):
        """Should map technical names to friendly names via humanizer."""
        profiles = agent_room_service.get_agent_profiles()

        # Find nexo_import agent
        nexo_profile = next(p for p in profiles if p["id"] == "nexo_import")
        assert nexo_profile["friendlyName"] == "NEXO"
        assert nexo_profile["description"] == "Seu assistente principal de importacao"

    def test_default_status_idle(self):
        """Should default to 'disponivel' status when no session_statuses provided."""
        profiles = agent_room_service.get_agent_profiles()

        for profile in profiles:
            assert profile["status"] == "disponivel"
            assert profile["statusLabel"] == "Disponivel"

    def test_uses_session_statuses(self):
        """Should use provided session_statuses to set agent status."""
        session_statuses = {
            "nexo_import": "processing",
            "intake": "pending_hil",
        }

        profiles = agent_room_service.get_agent_profiles(session_statuses)

        nexo = next(p for p in profiles if p["id"] == "nexo_import")
        assert nexo["status"] == "trabalhando"

        intake = next(p for p in profiles if p["id"] == "intake")
        assert intake["status"] == "esperando_voce"

    def test_agent_icons_mapping(self):
        """Should map friendly names to correct icons."""
        profiles = agent_room_service.get_agent_profiles()

        nexo = next(p for p in profiles if p["id"] == "nexo_import")
        assert nexo["avatar"] == "Bot"

        intake = next(p for p in profiles if p["id"] == "intake")
        assert intake["avatar"] == "FileText"

    def test_agent_colors_mapping(self):
        """Should map friendly names to correct colors."""
        profiles = agent_room_service.get_agent_profiles()

        nexo = next(p for p in profiles if p["id"] == "nexo_import")
        assert nexo["color"] == "magenta"

        intake = next(p for p in profiles if p["id"] == "intake")
        assert intake["color"] == "blue"

    def test_agent_order_preserved(self):
        """Should return agents in PRIMARY_AGENTS order."""
        profiles = agent_room_service.get_agent_profiles()

        expected_order = [
            "nexo_import", "intake", "import",
            "estoque_control", "compliance", "reconciliacao",
            "expedition", "carrier", "reverse",
            "schema_evolution", "learning",
            # AUDIT-004/2: equipment_research removed - dead code replaced by enrichment agent
            "observation", "comunicacao",
            # BUG-025: Strands structured output agents
            "file_analyzer", "vision_analyzer",
        ]

        actual_order = [p["id"] for p in profiles]
        assert actual_order == expected_order


# =============================================================================
# Test get_recent_events()
# =============================================================================

class TestGetRecentEvents:
    """Test get_recent_events function."""

    def test_queries_audit_log_for_date_range(self, mock_dynamodb_client):
        """Should query audit log for each day in range."""
        with patch('tools.agent_room_service.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2026, 1, 11, 10, 30, 0)
            mock_dynamodb_client.query_pk.return_value = []

            agent_room_service.get_recent_events(days_back=3, limit=50, db_client=mock_dynamodb_client)

            # Should query 3 days
            assert mock_dynamodb_client.query_pk.call_count == 3

            expected_calls = [
                call("LOG#2026-01-11", limit=50),
                call("LOG#2026-01-10", limit=50),
                call("LOG#2026-01-09", limit=50),
            ]
            mock_dynamodb_client.query_pk.assert_has_calls(expected_calls, any_order=True)

    def test_returns_humanized_events(self, mock_dynamodb_client, sample_audit_event):
        """Should return humanized events with correct structure."""
        mock_dynamodb_client.query_pk.return_value = [sample_audit_event]

        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        assert len(events) == 1
        event = events[0]

        assert "id" in event
        assert "timestamp" in event
        assert "agentName" in event
        assert "message" in event
        assert "type" in event
        assert "eventType" in event

    def test_sorts_events_by_timestamp_descending(self, mock_dynamodb_client):
        """Should sort events newest first."""
        events_data = [
            {"event_id": "1", "timestamp": "2026-01-11T10:00:00.000Z",
             "event_type": "AGENT_ACTIVITY", "actor_id": "nexo_import",
             "details": {"agent_id": "nexo_import", "status": "trabalhando",
                        "message": "Old event"}},
            {"event_id": "2", "timestamp": "2026-01-11T10:30:00.000Z",
             "event_type": "AGENT_ACTIVITY", "actor_id": "nexo_import",
             "details": {"agent_id": "nexo_import", "status": "trabalhando",
                        "message": "New event"}},
        ]
        mock_dynamodb_client.query_pk.return_value = events_data

        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        assert events[0]["id"] == "2"  # Newest first
        assert events[1]["id"] == "1"

    def test_limits_results(self, mock_dynamodb_client):
        """Should limit results to specified limit."""
        # Create 100 events
        events_data = []
        for i in range(100):
            events_data.append({
                "event_id": f"evt_{i}",
                "timestamp": f"2026-01-11T10:00:{i:02d}.000Z",
                "event_type": "AGENT_ACTIVITY",
                "actor_id": "nexo_import",
                "details": {"agent_id": "nexo_import", "status": "trabalhando",
                           "message": f"Event {i}"}
            })

        mock_dynamodb_client.query_pk.return_value = events_data

        events = agent_room_service.get_recent_events(limit=10, db_client=mock_dynamodb_client)

        assert len(events) == 10

    def test_handles_query_errors_gracefully(self, mock_dynamodb_client, capsys):
        """Should handle query errors and continue."""
        mock_dynamodb_client.query_pk.side_effect = Exception("DynamoDB error")

        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        assert events == []

        # Check error was logged
        captured = capsys.readouterr()
        assert "Error querying audit log" in captured.out

    def test_uses_provided_db_client(self, mock_dynamodb_client, sample_audit_event):
        """Should use provided db_client instead of creating new one."""
        mock_dynamodb_client.query_pk.return_value = [sample_audit_event]

        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        assert len(events) == 1

    def test_uses_audit_table_from_environment(self):
        """Should use audit table name from environment."""
        import os
        os.environ["AUDIT_LOG_TABLE"] = "custom-audit-table"

        with patch('tools.dynamodb_client.SGADynamoDBClient') as mock_db_class:
            mock_db_client = MagicMock()
            mock_db_class.return_value = mock_db_client
            mock_db_client.query_pk.return_value = []

            # Don't pass db_client so it creates one internally
            agent_room_service.get_recent_events()

            # Check it was called with custom table name
            mock_db_class.assert_called_once_with(table_name="custom-audit-table")


# =============================================================================
# Test get_learning_stories()
# =============================================================================

class TestGetLearningStories:
    """Test get_learning_stories function."""

    def test_returns_empty_list(self):
        """Should return empty list (TODO: integrate with AgentCore Memory)."""
        stories = agent_room_service.get_learning_stories()

        assert isinstance(stories, list)
        assert len(stories) == 0

    def test_accepts_limit_parameter(self):
        """Should accept limit parameter without error."""
        stories = agent_room_service.get_learning_stories(limit=5)

        assert isinstance(stories, list)


# =============================================================================
# Test get_active_workflow()
# =============================================================================

class TestGetActiveWorkflow:
    """Test get_active_workflow function."""

    def test_returns_none_without_session_id(self):
        """Should return None when no session_id provided."""
        workflow = agent_room_service.get_active_workflow()

        assert workflow is None

    def test_returns_none_with_session_id(self):
        """Should return None with session_id (TODO: integrate with SessionManager)."""
        workflow = agent_room_service.get_active_workflow(session_id="session_123")

        assert workflow is None


# =============================================================================
# Test get_pending_decisions()
# =============================================================================

class TestGetPendingDecisions:
    """Test get_pending_decisions function."""

    def test_queries_pending_hil_tasks(self, mock_dynamodb_client):
        """Should query pending HIL tasks via GSI."""
        mock_dynamodb_client.query_gsi.return_value = []

        agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        mock_dynamodb_client.query_gsi.assert_called_once_with(
            gsi_name="GSI1",
            pk_value="USER#user_123",
            sk_prefix="TASK#PENDING#",
            limit=20,
        )

    def test_returns_humanized_decisions(self, mock_dynamodb_client, sample_hil_task):
        """Should return humanized decisions with correct structure."""
        mock_dynamodb_client.query_gsi.return_value = [sample_hil_task]

        decisions = agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        assert len(decisions) == 1
        decision = decisions[0]

        assert "id" in decision
        assert "question" in decision
        assert "options" in decision
        assert "priority" in decision
        assert "createdAt" in decision
        assert "taskType" in decision
        assert "entityId" in decision

    def test_humanizes_hil_questions(self, mock_dynamodb_client, sample_hil_task):
        """Should humanize HIL questions using templates."""
        mock_dynamodb_client.query_gsi.return_value = [sample_hil_task]

        decisions = agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        assert decisions[0]["question"] == "Encontrei uma nota fiscal. Posso importar os 25 itens?"

    def test_provides_hil_options(self, mock_dynamodb_client, sample_hil_task):
        """Should provide humanized options for HIL task."""
        mock_dynamodb_client.query_gsi.return_value = [sample_hil_task]

        decisions = agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        options = decisions[0]["options"]
        assert len(options) == 2
        assert options[0]["label"] == "Sim, importar"
        assert options[0]["action"] == "approve"

    def test_handles_query_errors_gracefully(self, mock_dynamodb_client, capsys):
        """Should handle query errors and return empty list."""
        mock_dynamodb_client.query_gsi.side_effect = Exception("DynamoDB error")

        decisions = agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        assert decisions == []

        # Check error was logged
        captured = capsys.readouterr()
        assert "Error getting pending decisions" in captured.out

    def test_uses_provided_db_client(self, mock_dynamodb_client, sample_hil_task):
        """Should use provided db_client instead of creating new one."""
        mock_dynamodb_client.query_gsi.return_value = [sample_hil_task]

        decisions = agent_room_service.get_pending_decisions(
            user_id="user_123",
            db_client=mock_dynamodb_client
        )

        assert len(decisions) == 1


# =============================================================================
# Test _humanize_hil_question()
# =============================================================================

class TestHumanizeHilQuestion:
    """Test _humanize_hil_question function."""

    def test_confirm_nf_entry_template(self):
        """Should format confirm_nf_entry question."""
        question = agent_room_service._humanize_hil_question(
            "confirm_nf_entry",
            {"count": 25, "nf_number": "123456"}
        )

        assert question == "Encontrei uma nota fiscal. Posso importar os 25 itens?"

    def test_create_new_pn_template(self):
        """Should format create_new_pn question."""
        question = agent_room_service._humanize_hil_question(
            "create_new_pn",
            {"description": "Bomba Centrifuga"}
        )

        assert question == "Encontrei um item novo: Bomba Centrifuga. Posso criar o cadastro?"

    def test_create_column_template(self):
        """Should format create_column question."""
        question = agent_room_service._humanize_hil_question(
            "create_column",
            {"column": "fabricante"}
        )

        assert question == "Seus dados tem um campo novo: 'fabricante'. Posso criar essa coluna?"

    def test_resolve_mapping_template(self):
        """Should format resolve_mapping question."""
        question = agent_room_service._humanize_hil_question(
            "resolve_mapping",
            {"source": "qtd"}
        )

        assert question == "Nao consegui mapear 'qtd'. Qual coluna devo usar?"

    def test_approve_import_template(self):
        """Should format approve_import question."""
        question = agent_room_service._humanize_hil_question(
            "approve_import",
            {"count": 150}
        )

        assert question == "Tenho 150 itens prontos. Posso importar?"

    def test_review_divergence_template(self):
        """Should format review_divergence question."""
        question = agent_room_service._humanize_hil_question(
            "review_divergence",
            {"item": "BOM-123"}
        )

        assert question == "Encontrei uma divergencia no item BOM-123. O que devo fazer?"

    def test_unknown_task_type_default(self):
        """Should return default message for unknown task type."""
        question = agent_room_service._humanize_hil_question(
            "unknown_task",
            {}
        )

        assert question == "Preciso da sua decisao sobre uma tarefa."

    def test_missing_template_data(self):
        """Should handle missing template data gracefully."""
        question = agent_room_service._humanize_hil_question(
            "confirm_nf_entry",
            {}  # Missing count
        )

        # Should return template as-is with placeholders
        assert "{count}" in question or question == "Encontrei uma nota fiscal. Posso importar os {count} itens?"


# =============================================================================
# Test _get_hil_options()
# =============================================================================

class TestGetHilOptions:
    """Test _get_hil_options function."""

    def test_confirm_nf_entry_options(self):
        """Should return options for confirm_nf_entry."""
        options = agent_room_service._get_hil_options("confirm_nf_entry")

        assert len(options) == 2
        assert options[0] == {"label": "Sim, importar", "action": "approve"}
        assert options[1] == {"label": "Revisar primeiro", "action": "review"}

    def test_create_new_pn_options(self):
        """Should return options for create_new_pn."""
        options = agent_room_service._get_hil_options("create_new_pn")

        assert len(options) == 2
        assert options[0] == {"label": "Criar cadastro", "action": "approve"}
        assert options[1] == {"label": "Ignorar", "action": "reject"}

    def test_create_column_options(self):
        """Should return options for create_column."""
        options = agent_room_service._get_hil_options("create_column")

        assert len(options) == 3
        assert options[0] == {"label": "Criar coluna", "action": "approve"}
        assert options[1] == {"label": "Usar metadata", "action": "metadata"}
        assert options[2] == {"label": "Ignorar", "action": "reject"}

    def test_approve_import_options(self):
        """Should return options for approve_import."""
        options = agent_room_service._get_hil_options("approve_import")

        assert len(options) == 2
        assert options[0] == {"label": "Importar", "action": "approve"}
        assert options[1] == {"label": "Cancelar", "action": "reject"}

    def test_unknown_task_type_default(self):
        """Should return default options for unknown task type."""
        options = agent_room_service._get_hil_options("unknown_task")

        assert len(options) == 2
        assert options[0] == {"label": "Aprovar", "action": "approve"}
        assert options[1] == {"label": "Rejeitar", "action": "reject"}


# =============================================================================
# Test emit_agent_event()
# =============================================================================

class TestEmitAgentEvent:
    """Test emit_agent_event function."""

    def test_emits_event_to_audit_log(self, mock_audit_logger):
        """Should emit event to audit log."""
        with patch('tools.dynamodb_client.SGAAuditLogger') as mock_logger_class:
            mock_logger_class.return_value = mock_audit_logger
            mock_audit_logger.log_event.return_value = True

            result = agent_room_service.emit_agent_event(
                agent_id="nexo_import",
                status="trabalhando",
                message="Analisando arquivo CSV...",
            )

            assert result is True
            mock_audit_logger.log_event.assert_called_once()

    def test_event_has_correct_structure(self, mock_audit_logger):
        """Should emit event with correct structure."""
        with patch('tools.dynamodb_client.SGAAuditLogger') as mock_logger_class:
            mock_logger_class.return_value = mock_audit_logger
            mock_audit_logger.log_event.return_value = True

            agent_room_service.emit_agent_event(
                agent_id="nexo_import",
                status="trabalhando",
                message="Analisando arquivo...",
                session_id="session_123",
                details={"file_size": 1024}
            )

            call_kwargs = mock_audit_logger.log_event.call_args[1]

            assert call_kwargs["event_type"] == "AGENT_ACTIVITY"
            assert call_kwargs["actor_type"] == "AGENT"
            assert call_kwargs["actor_id"] == "nexo_import"
            assert call_kwargs["entity_type"] == "agent_status"
            assert call_kwargs["entity_id"] == "nexo_import"
            assert call_kwargs["action"] == "trabalhando"
            assert call_kwargs["session_id"] == "session_123"

            details = call_kwargs["details"]
            assert details["agent_id"] == "nexo_import"
            assert details["status"] == "trabalhando"
            assert details["message"] == "Analisando arquivo..."
            assert details["file_size"] == 1024

    def test_works_without_optional_parameters(self, mock_audit_logger):
        """Should work without session_id and details."""
        with patch('tools.dynamodb_client.SGAAuditLogger') as mock_logger_class:
            mock_logger_class.return_value = mock_audit_logger
            mock_audit_logger.log_event.return_value = True

            result = agent_room_service.emit_agent_event(
                agent_id="intake",
                status="disponivel",
                message="Pronto para receber notas fiscais",
            )

            assert result is True

    def test_returns_false_on_error(self, mock_audit_logger):
        """Should return False if logging fails."""
        with patch('tools.dynamodb_client.SGAAuditLogger') as mock_logger_class:
            mock_logger_class.return_value = mock_audit_logger
            mock_audit_logger.log_event.return_value = False

            result = agent_room_service.emit_agent_event(
                agent_id="data_import",  # Renamed from "import" (Python reserved word)
                status="problema",
                message="Erro ao importar",
            )

            assert result is False


# =============================================================================
# Test get_agent_room_data()
# =============================================================================

class TestGetAgentRoomData:
    """Test get_agent_room_data main aggregation function."""

    @patch('tools.agent_room_service.get_pending_decisions')
    @patch('tools.agent_room_service.get_active_workflow')
    @patch('tools.agent_room_service.get_learning_stories')
    @patch('tools.agent_room_service.get_recent_events')
    @patch('tools.agent_room_service.get_agent_profiles')
    def test_aggregates_all_data(self, mock_profiles, mock_events, mock_stories,
                                  mock_workflow, mock_decisions):
        """Should aggregate data from all sources."""
        mock_profiles.return_value = [{"id": "nexo_import"}]
        mock_events.return_value = [{"id": "evt_1"}]
        mock_stories.return_value = []
        mock_workflow.return_value = None
        mock_decisions.return_value = [{"id": "task_1"}]

        data = agent_room_service.get_agent_room_data(
            user_id="user_123",
            session_id="session_123"
        )

        assert data["success"] is True
        assert "timestamp" in data
        assert data["agents"] == [{"id": "nexo_import"}]
        assert data["liveFeed"] == [{"id": "evt_1"}]
        assert data["learningStories"] == []
        assert data["activeWorkflow"] is None
        assert data["pendingDecisions"] == [{"id": "task_1"}]

    @patch('tools.agent_room_service.get_pending_decisions')
    @patch('tools.agent_room_service.get_active_workflow')
    @patch('tools.agent_room_service.get_learning_stories')
    @patch('tools.agent_room_service.get_recent_events')
    @patch('tools.agent_room_service.get_agent_profiles')
    def test_passes_correct_parameters(self, mock_profiles, mock_events, mock_stories,
                                       mock_workflow, mock_decisions):
        """Should pass correct parameters to sub-functions."""
        mock_profiles.return_value = []
        mock_events.return_value = []
        mock_stories.return_value = []
        mock_workflow.return_value = None
        mock_decisions.return_value = []

        agent_room_service.get_agent_room_data(
            user_id="user_123",
            session_id="session_123"
        )

        mock_profiles.assert_called_once_with()
        mock_events.assert_called_once_with(days_back=1, limit=30)
        mock_stories.assert_called_once_with(limit=5)
        mock_workflow.assert_called_once_with("session_123")
        mock_decisions.assert_called_once_with("user_123")

    @patch('tools.agent_room_service.get_pending_decisions')
    @patch('tools.agent_room_service.get_active_workflow')
    @patch('tools.agent_room_service.get_learning_stories')
    @patch('tools.agent_room_service.get_recent_events')
    @patch('tools.agent_room_service.get_agent_profiles')
    def test_does_not_share_db_client(self, mock_profiles, mock_events, mock_stories,
                                      mock_workflow, mock_decisions):
        """Should not pass shared db_client (functions use different tables)."""
        mock_profiles.return_value = []
        mock_events.return_value = []
        mock_stories.return_value = []
        mock_workflow.return_value = None
        mock_decisions.return_value = []

        agent_room_service.get_agent_room_data(user_id="user_123")

        # Verify no db_client was passed (functions create their own)
        mock_events.assert_called_with(days_back=1, limit=30)
        mock_decisions.assert_called_with("user_123")

    @patch('tools.agent_room_service.datetime')
    @patch('tools.agent_room_service.get_pending_decisions')
    @patch('tools.agent_room_service.get_active_workflow')
    @patch('tools.agent_room_service.get_learning_stories')
    @patch('tools.agent_room_service.get_recent_events')
    @patch('tools.agent_room_service.get_agent_profiles')
    def test_includes_timestamp(self, mock_profiles, mock_events, mock_stories,
                                mock_workflow, mock_decisions, mock_datetime):
        """Should include ISO timestamp with Z suffix."""
        mock_datetime.utcnow.return_value = datetime(2026, 1, 11, 10, 30, 0)
        mock_profiles.return_value = []
        mock_events.return_value = []
        mock_stories.return_value = []
        mock_workflow.return_value = None
        mock_decisions.return_value = []

        data = agent_room_service.get_agent_room_data(user_id="user_123")

        assert data["timestamp"] == "2026-01-11T10:30:00Z"


# =============================================================================
# Test _get_audit_table()
# =============================================================================

class TestGetAuditTable:
    """Test _get_audit_table helper function."""

    def test_returns_env_variable(self):
        """Should return audit table name from environment."""
        import os
        os.environ["AUDIT_LOG_TABLE"] = "custom-audit-table"

        table_name = agent_room_service._get_audit_table()

        assert table_name == "custom-audit-table"

    def test_returns_default_when_env_not_set(self):
        """Should return default table name when env var not set."""
        import os
        if "AUDIT_LOG_TABLE" in os.environ:
            del os.environ["AUDIT_LOG_TABLE"]

        table_name = agent_room_service._get_audit_table()

        assert table_name == "faiston-one-sga-audit-log-prod"


# =============================================================================
# Integration Tests
# =============================================================================

class TestAgentRoomServiceIntegration:
    """Integration tests for Agent Room Service."""

    @pytest.mark.integration
    def test_emit_and_retrieve_flow(self, mock_audit_logger, mock_dynamodb_client, sample_audit_event):
        """Should be able to emit event and retrieve it."""
        # Setup emit
        with patch('tools.dynamodb_client.SGAAuditLogger') as mock_logger_class:
            mock_logger_class.return_value = mock_audit_logger
            mock_audit_logger.log_event.return_value = True

            # Emit event
            emit_result = agent_room_service.emit_agent_event(
                agent_id="nexo_import",
                status="trabalhando",
                message="Analisando arquivo CSV com 1,658 linhas...",
            )

            assert emit_result is True

        # Setup retrieve
        mock_dynamodb_client.query_pk.return_value = [sample_audit_event]

        # Retrieve events
        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        assert len(events) == 1
        assert events[0]["agentName"] == "NEXO"
        assert events[0]["message"] == "Analisando arquivo CSV com 1,658 linhas..."

    @pytest.mark.integration
    def test_full_agent_room_data_structure(self):
        """Should return complete Agent Room data structure."""
        with patch('tools.dynamodb_client.SGADynamoDBClient') as mock_db_class:
            mock_db_client = MagicMock()
            mock_db_class.return_value = mock_db_client
            mock_db_client.query_pk.return_value = []
            mock_db_client.query_gsi.return_value = []

            data = agent_room_service.get_agent_room_data(user_id="user_123")

            # Verify top-level structure
            assert data["success"] is True
            assert isinstance(data["timestamp"], str)
            assert isinstance(data["agents"], list)
            assert isinstance(data["liveFeed"], list)
            assert isinstance(data["learningStories"], list)
            assert isinstance(data["pendingDecisions"], list)
            assert data["activeWorkflow"] is None

            # Verify agents
            assert len(data["agents"]) == 14

            # Verify all agents have required fields
            for agent in data["agents"]:
                assert "friendlyName" in agent
                assert "description" in agent
                assert "status" in agent


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_session_statuses_dict(self):
        """Should handle empty session_statuses dict."""
        profiles = agent_room_service.get_agent_profiles(session_statuses={})

        assert len(profiles) == 14
        assert all(p["status"] == "disponivel" for p in profiles)

    def test_none_session_statuses(self):
        """Should handle None session_statuses."""
        profiles = agent_room_service.get_agent_profiles(session_statuses=None)

        assert len(profiles) == 14

    def test_malformed_audit_events(self, mock_dynamodb_client):
        """Should handle malformed audit events gracefully."""
        # Malformed event missing required fields
        malformed_event = {
            "event_id": "bad_event",
            # Missing most required fields
        }

        mock_dynamodb_client.query_pk.return_value = [malformed_event]

        events = agent_room_service.get_recent_events(db_client=mock_dynamodb_client)

        # Should still return event with defaults (graceful degradation)
        assert len(events) == 1
        assert events[0]["id"] == "bad_event"
        assert events[0]["agentName"] == "Sistema"  # Default agent name
        assert "message" in events[0]  # Some message provided

    def test_malformed_hil_tasks(self, mock_dynamodb_client):
        """Should handle malformed HIL tasks gracefully."""
        # Task missing details
        malformed_task = {
            "task_id": "bad_task",
            "task_type": "unknown_type",
            # Missing details and other fields
        }

        mock_dynamodb_client.query_gsi.return_value = [malformed_task]

        decisions = agent_room_service.get_pending_decisions(user_id="user_123", db_client=mock_dynamodb_client)

        assert len(decisions) == 1
        # Should use defaults for missing fields
        assert decisions[0]["priority"] == "normal"
        assert "createdAt" in decisions[0]

    def test_zero_limit(self):
        """Should handle zero limit."""
        stories = agent_room_service.get_learning_stories(limit=0)

        assert stories == []

    def test_negative_days_back(self):
        """Should handle negative days_back gracefully."""
        # This is an edge case - function doesn't validate input
        # but should not crash
        events = agent_room_service.get_recent_events(days_back=-1)

        # Should return empty or handle gracefully
        assert isinstance(events, list)
