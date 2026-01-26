# =============================================================================
# Agent Card Validation Tests - AUDIT-002 Compliance
# =============================================================================
# Tests to verify that all agents define proper Agent Cards (A2A Protocol).
#
# Each agent MUST define:
# - AGENT_ID: Unique identifier
# - AGENT_NAME: Human-readable name
# - RUNTIME_ID: AgentCore deployment ID
# - AGENT_SKILLS: List of AgentSkill objects for discovery
#
# Reference:
# - A2A Protocol: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
# - Agent Card discovery at /.well-known/agent-card.json
# =============================================================================

import pytest
import importlib
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAgentCardCompliance:
    """Test Agent Card compliance for all inventory agents."""

    # List of all agents that should have Agent Cards
    # Format: (module_path, agent_id_contains)
    # NOTE: Some agents use "faiston_" prefix, some don't - we check contains
    SPECIALIST_AGENTS = [
        ("agents.specialists.debug.main", "debug"),
        ("agents.specialists.inventory_analyst.main", "inventory_analyst"),
        ("agents.specialists.schema_mapper.main", "schema_mapper"),
        ("agents.specialists.data_transformer.main", "data_transformer"),
        ("agents.specialists.observation.main", "observation"),
        ("agents.specialists.repair.main", "repair"),
    ]

    ORCHESTRATOR_AGENTS = [
        ("agents.orchestrators.inventory_hub.main", "inventory_hub"),
    ]

    ALL_AGENTS = SPECIALIST_AGENTS + ORCHESTRATOR_AGENTS

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_specialist_agent_has_agent_id(self, module_path: str, agent_id_contains: str):
        """Specialist agents must have AGENT_ID constant."""
        try:
            module = importlib.import_module(module_path)
            assert hasattr(module, "AGENT_ID"), f"{module_path} missing AGENT_ID constant"
            # AGENT_ID may have "faiston_" prefix - just check it contains the expected part
            assert agent_id_contains in module.AGENT_ID, (
                f"{module_path} AGENT_ID should contain '{agent_id_contains}', "
                f"got '{module.AGENT_ID}'"
            )
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_specialist_agent_has_agent_name(self, module_path: str, agent_id_contains: str):
        """Specialist agents must have AGENT_NAME constant."""
        try:
            module = importlib.import_module(module_path)
            assert hasattr(module, "AGENT_NAME"), f"{module_path} missing AGENT_NAME constant"
            assert isinstance(module.AGENT_NAME, str), f"{module_path} AGENT_NAME must be string"
            assert len(module.AGENT_NAME) > 0, f"{module_path} AGENT_NAME must not be empty"
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_specialist_agent_has_runtime_id(self, module_path: str, agent_id_contains: str):
        """Specialist agents must have RUNTIME_ID constant (AgentCore deployment)."""
        try:
            module = importlib.import_module(module_path)
            assert hasattr(module, "RUNTIME_ID"), f"{module_path} missing RUNTIME_ID constant"
            assert isinstance(module.RUNTIME_ID, str), f"{module_path} RUNTIME_ID must be string"
            # Check it's not a placeholder
            if "PLACEHOLDER" in module.RUNTIME_ID:
                pytest.skip(f"{module_path} RUNTIME_ID is placeholder (not deployed yet)")
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_specialist_agent_has_agent_skills(self, module_path: str, agent_id_contains: str):
        """Specialist agents must have AGENT_SKILLS list."""
        try:
            module = importlib.import_module(module_path)
            assert hasattr(module, "AGENT_SKILLS"), f"{module_path} missing AGENT_SKILLS list"
            assert isinstance(module.AGENT_SKILLS, list), f"{module_path} AGENT_SKILLS must be list"
            assert len(module.AGENT_SKILLS) > 0, f"{module_path} AGENT_SKILLS must not be empty"
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_agent_skills_have_required_fields(self, module_path: str, agent_id_contains: str):
        """AgentSkill objects must have id, name, description."""
        try:
            module = importlib.import_module(module_path)
            if not hasattr(module, "AGENT_SKILLS"):
                pytest.skip(f"{module_path} has no AGENT_SKILLS")

            for skill in module.AGENT_SKILLS:
                # Check required fields
                assert hasattr(skill, "id") and skill.id, f"Skill missing 'id' in {module_path}"
                assert hasattr(skill, "name") and skill.name, f"Skill missing 'name' in {module_path}"
                assert hasattr(skill, "description") and skill.description, (
                    f"Skill {skill.id} missing 'description' in {module_path}"
                )
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_agent_skills_have_unique_ids(self, module_path: str, agent_id_contains: str):
        """AgentSkill IDs must be unique within an agent."""
        try:
            module = importlib.import_module(module_path)
            if not hasattr(module, "AGENT_SKILLS"):
                pytest.skip(f"{module_path} has no AGENT_SKILLS")

            skill_ids = [skill.id for skill in module.AGENT_SKILLS]
            duplicates = [x for x in skill_ids if skill_ids.count(x) > 1]
            assert len(duplicates) == 0, (
                f"Duplicate skill IDs in {module_path}: {set(duplicates)}"
            )
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")


class TestAgentSkillQuality:
    """Test Agent Skill quality standards."""

    SPECIALIST_AGENTS = TestAgentCardCompliance.SPECIALIST_AGENTS

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_skill_descriptions_not_too_short(self, module_path: str, agent_id_contains: str):
        """Skill descriptions should be descriptive (>20 chars)."""
        try:
            module = importlib.import_module(module_path)
            if not hasattr(module, "AGENT_SKILLS"):
                pytest.skip(f"{module_path} has no AGENT_SKILLS")

            for skill in module.AGENT_SKILLS:
                if hasattr(skill, "description") and skill.description:
                    assert len(skill.description) > 20, (
                        f"Skill '{skill.id}' description too short (<20 chars) in {module_path}"
                    )
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")

    @pytest.mark.parametrize("module_path,agent_id_contains", SPECIALIST_AGENTS)
    def test_skill_names_proper_case(self, module_path: str, agent_id_contains: str):
        """Skill names should be Title Case or proper naming."""
        try:
            module = importlib.import_module(module_path)
            if not hasattr(module, "AGENT_SKILLS"):
                pytest.skip(f"{module_path} has no AGENT_SKILLS")

            for skill in module.AGENT_SKILLS:
                if hasattr(skill, "name") and skill.name:
                    # Name should start with uppercase
                    assert skill.name[0].isupper(), (
                        f"Skill name '{skill.name}' should start with uppercase in {module_path}"
                    )
        except ImportError as e:
            pytest.skip(f"Cannot import {module_path}: {e}")


class TestRuntimeIdConsistency:
    """Test RUNTIME_ID consistency with strands_a2a_client.py registry."""

    def test_runtime_ids_match_registry(self):
        """Agent RUNTIME_IDs should match strands_a2a_client PROD_RUNTIME_IDS."""
        try:
            from shared.strands_a2a_client import PROD_RUNTIME_IDS

            # Check each agent that should be in the registry
            agents_to_check = [
                ("agents.specialists.debug.main", "debug"),
                ("agents.specialists.inventory_analyst.main", "inventory_analyst"),
                ("agents.specialists.schema_mapper.main", "schema_mapper"),
                ("agents.specialists.data_transformer.main", "data_transformer"),
                ("agents.specialists.observation.main", "observation"),
            ]

            for module_path, agent_id in agents_to_check:
                try:
                    module = importlib.import_module(module_path)
                    if hasattr(module, "RUNTIME_ID"):
                        module_runtime_id = module.RUNTIME_ID
                        if "PLACEHOLDER" not in module_runtime_id:
                            registry_runtime_id = PROD_RUNTIME_IDS.get(agent_id)
                            if registry_runtime_id and "PLACEHOLDER" not in registry_runtime_id:
                                assert module_runtime_id == registry_runtime_id, (
                                    f"RUNTIME_ID mismatch for {agent_id}: "
                                    f"module has '{module_runtime_id}', "
                                    f"registry has '{registry_runtime_id}'"
                                )
                except ImportError:
                    continue  # Skip agents that can't be imported

        except ImportError as e:
            pytest.skip(f"Cannot import a2a_client: {e}")
