#!/usr/bin/env python3
# =============================================================================
# Agent Structure Validation Script - Strands A2A Architecture (ADR-002)
# =============================================================================
# Validates all agents follow the correct AgentCore pattern.
#
# ARCHITECTURE: "Everything is an Agent" (ADR-002)
# - ORCHESTRATORS in agents/orchestrators/{domain}/
# - SPECIALISTS in agents/specialists/{agent_name}/
# - Each agent has its OWN main.py with Strands A2AServer
# - ReAct pattern: OBSERVE → THINK → LEARN → ACT + HIL
#
# CURRENT STATE (January 2026):
# - Orchestrator: inventory_hub (Phases 1-4 Smart Import)
# - Specialists: debug, inventory_analyst, schema_mapper, data_transformer
# - Logistics agents (carrier, expedition, reverse, reconciliacao) are in agentcore-carrier
# =============================================================================

import sys
from pathlib import Path
from typing import List, Tuple

# Directory structure (ADR-002)
SPECIALISTS_SUBDIR = "specialists"
ORCHESTRATORS_SUBDIR = "orchestrators"

# Expected specialist agents (January 2026)
# NOTE: Logistics agents (carrier, expedition, reverse, reconciliacao) belong to agentcore-carrier project
EXPECTED_AGENTS = [
    "debug",  # faiston_sga_debug - AI-powered error analysis with Gemini 2.5 Pro + Thinking
    "inventory_analyst",  # faiston_inventory_analyst - Phase 2 file structure analysis
    "schema_mapper",  # faiston_schema_mapper - Phase 3 column mapping to schema
    "data_transformer",  # faiston_data_transformer - Phase 4 ETL with Fire-and-Forget
]

# Expected orchestrators (January 2026)
EXPECTED_ORCHESTRATORS = [
    "inventory_hub",  # faiston_sga_inventory_hub - Central intelligence for SGA (Phases 1-4)
]

# Agent roles for documentation
AGENT_ROLES = {
    "debug": "SPECIALIST (AI-Powered Error Analysis)",
    "inventory_analyst": "SPECIALIST (Phase 2 - File Structure Analysis)",
    "schema_mapper": "SPECIALIST (Phase 3 - Column Mapping to Schema)",
    "data_transformer": "SPECIALIST (Phase 4 - Cognitive ETL with Fire-and-Forget)",
}

# Orchestrator roles
ORCHESTRATOR_ROLES = {
    "inventory_hub": "ORCHESTRATOR (SGA Inventory Hub - Phases 1-4)",
}

# Required files for each agent subdirectory
# NOTE: agent.py REMOVED - legacy Google ADK format. Now using Strands A2A via main.py only.
# NOTE: Dockerfile REMOVED - ADR-001 mandates ZIP deploy with AgentCore, not Docker.
# NOTE: requirements.txt is at PROJECT ROOT level, not per-agent (shared dependencies)
REQUIRED_FILES = [
    "__init__.py",
    "main.py",  # Strands A2AServer entry point (replaced agent.py)
    # requirements.txt is shared at project root - not per-agent
]

# Required in tools directory
REQUIRED_TOOLS = [
    "__init__.py",
]


def validate_agent_structure(agents_dir: Path) -> Tuple[bool, List[str]]:
    """Validate all agents have the correct structure."""
    errors = []
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR

    for agent_name in EXPECTED_AGENTS:
        agent_dir = specialists_dir / agent_name

        # Check agent directory exists
        if not agent_dir.exists():
            errors.append(f"❌ Missing agent directory: {agent_name}")
            continue

        # Check required files
        for file_name in REQUIRED_FILES:
            file_path = agent_dir / file_name
            if not file_path.exists():
                errors.append(f"❌ {agent_name}: Missing {file_name}")

        # Check tools directory OR inline tools in main.py
        tools_dir = agent_dir / "tools"
        main_py = agent_dir / "main.py"
        has_inline_tools = main_py.exists() and "@tool" in main_py.read_text()

        if not tools_dir.exists() and not has_inline_tools:
            errors.append(f"❌ {agent_name}: Missing tools/ directory and no inline @tool in main.py")
        elif tools_dir.exists():
            # Check tools __init__.py
            tools_init = tools_dir / "__init__.py"
            if not tools_init.exists():
                errors.append(f"❌ {agent_name}: Missing tools/__init__.py")

            # Check at least one tool file exists
            tool_files = [f for f in tools_dir.glob("*.py") if f.name != "__init__.py"]
            if not tool_files:
                errors.append(f"⚠️  {agent_name}: No tool files in tools/")
        # else: has inline tools in main.py, which is valid

    return len(errors) == 0, errors


def validate_shared_module(base_dir: Path) -> Tuple[bool, List[str]]:
    """Validate shared module exists with required files."""
    errors = []
    shared_dir = base_dir / "shared"

    if not shared_dir.exists():
        errors.append("❌ Missing shared/ directory")
        return False, errors

    required_shared = [
        "__init__.py",
        "audit_emitter.py",
        "a2a_client.py",
        "xray_tracer.py",
    ]

    for file_name in required_shared:
        file_path = shared_dir / file_name
        if not file_path.exists():
            errors.append(f"❌ shared/: Missing {file_name}")

    return len(errors) == 0, errors


def validate_per_agent_main(agents_dir: Path) -> Tuple[bool, List[str]]:
    """Validate each agent has its own main.py with Strands A2AServer."""
    errors = []
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR

    for agent_name in EXPECTED_AGENTS:
        main_py = specialists_dir / agent_name / "main.py"

        if not main_py.exists():
            errors.append(f"❌ {agent_name}: Missing main.py")
            continue

        content = main_py.read_text()

        # Check for Strands imports
        if "from strands" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing Strands imports")

        # Check for A2AServer (some agents use FastAPI directly for A2A)
        if "A2AServer" not in content and "FastAPI" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing A2AServer or FastAPI")

        # Check for @tool decorator
        if "@tool" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing @tool decorators")

    return len(errors) == 0, errors


def validate_dockerfile_content(agents_dir: Path) -> Tuple[bool, List[str]]:
    """Validate Dockerfiles have correct settings."""
    errors = []
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR

    for agent_name in EXPECTED_AGENTS:
        dockerfile = specialists_dir / agent_name / "Dockerfile"
        if not dockerfile.exists():
            continue

        content = dockerfile.read_text()

        # Check ARM64 platform
        if "linux/arm64" not in content:
            errors.append(f"⚠️  {agent_name}: Dockerfile missing ARM64 platform")

        # Check Python 3.13
        if "python:3.13" not in content:
            errors.append(f"⚠️  {agent_name}: Dockerfile not using Python 3.13")

        # Check port 9000
        if "9000" not in content:
            errors.append(f"⚠️  {agent_name}: Dockerfile not exposing port 9000")

    return len(errors) == 0, errors


def validate_agent_id(agents_dir: Path) -> Tuple[bool, List[str]]:
    """Validate each agent has correct AGENT_ID in main.py."""
    errors = []
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR

    for agent_name in EXPECTED_AGENTS:
        # Check main.py (primary) - this is the Strands A2AServer entry point
        main_file = specialists_dir / agent_name / "main.py"
        if main_file.exists():
            content = main_file.read_text()

            # Check AGENT_ID is defined
            if "AGENT_ID" not in content:
                errors.append(f"⚠️  {agent_name}: main.py missing AGENT_ID")

            # Check AGENT_NAME is defined
            if "AGENT_NAME" not in content:
                errors.append(f"⚠️  {agent_name}: main.py missing AGENT_NAME")

    return len(errors) == 0, errors


def validate_no_legacy_files(base_dir: Path) -> Tuple[bool, List[str]]:
    """Validate legacy files have been removed."""
    errors = []

    # Check no unified main_a2a.py exists
    main_a2a = base_dir / "main_a2a.py"
    if main_a2a.exists():
        errors.append("❌ Legacy main_a2a.py still exists (should be deleted)")

    # Check no shim agent files at root agents/ level
    legacy_shims = [
        "nexo_import_agent.py",
        "intake_agent.py",
        "estoque_control_agent.py",
        "nexo_estoque_agent.py",
    ]

    agents_dir = base_dir / "agents"
    for shim_file in legacy_shims:
        shim_path = agents_dir / shim_file
        if shim_path.exists():
            errors.append(f"❌ Legacy shim file still exists: agents/{shim_file}")

    # Check no estoque orchestrator (legacy)
    estoque_dir = agents_dir / ORCHESTRATORS_SUBDIR / "estoque"
    if estoque_dir.exists():
        errors.append("❌ Legacy orchestrator estoque/ still exists (should be deleted)")

    return len(errors) == 0, errors


def validate_orchestrator_structure(agents_dir: Path) -> Tuple[bool, List[str]]:
    """Validate orchestrator agents have the correct structure.

    NOTE: Orchestrators use tools from shared/tools/ directory (project-level),
    not from a local tools/ directory. They define tools inline or import from shared.
    """
    errors = []
    orchestrators_dir = agents_dir / ORCHESTRATORS_SUBDIR

    for orch_name in EXPECTED_ORCHESTRATORS:
        orch_dir = orchestrators_dir / orch_name

        # Check orchestrator directory exists
        if not orch_dir.exists():
            errors.append(f"❌ Missing orchestrator directory: {orch_name}")
            continue

        # Check required files (only __init__.py and main.py)
        for file_name in REQUIRED_FILES:
            file_path = orch_dir / file_name
            if not file_path.exists():
                errors.append(f"❌ {orch_name} (orchestrator): Missing {file_name}")

        # NOTE: Orchestrators don't require a local tools/ directory
        # They use tools from shared/ or import from other modules

    return len(errors) == 0, errors


def main():
    """Run all validations."""
    print("=" * 60)
    print("🔍 Agent Structure Validation (January 2026)")
    print("=" * 60)
    print()
    print("📝 Current architecture:")
    print("   - Orchestrator: inventory_hub (Phases 1-4 Smart Import)")
    print("   - Specialists: debug, inventory_analyst, schema_mapper, data_transformer")
    print("   - Logistics agents are managed in agentcore-carrier project.")
    print()

    # Determine paths
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent
    agents_dir = base_dir / "agents"

    all_valid = True
    all_errors = []

    # 1. Validate no legacy files
    print("🗑️  Checking legacy files removed...")
    valid, errors = validate_no_legacy_files(base_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ No legacy files' if valid else '❌ Legacy files found'}")

    # 2. Validate orchestrator structure
    print("📁 Checking orchestrator directory structure...")
    valid, errors = validate_orchestrator_structure(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ Orchestrator present' if valid else '❌ Issues found'}")

    # 3. Validate specialist agent structure
    print("📁 Checking specialist agent directory structure...")
    valid, errors = validate_agent_structure(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ All specialists present' if valid else '❌ Issues found'}")

    # 4. Validate shared module
    print("📦 Checking shared module...")
    valid, errors = validate_shared_module(base_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ Shared module complete' if valid else '❌ Issues found'}")

    # 5. Validate per-agent main.py (Strands A2AServer)
    print("🚀 Checking per-agent main.py (Strands A2AServer)...")
    valid, errors = validate_per_agent_main(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ All main.py files valid' if valid else '❌ Issues found'}")

    # 6. Dockerfiles - SKIPPED per ADR-001 (ZIP deploy, not Docker)
    print("🐳 Dockerfiles: SKIPPED (ADR-001: ZIP deploy)")

    # 7. Validate agent content
    print("🤖 Checking agent definitions...")
    valid, errors = validate_agent_id(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ Agent definitions valid' if valid else '⚠️  Warnings found'}")

    print()
    print("=" * 60)

    if all_errors:
        print("📋 Issues Found:")
        for error in all_errors:
            print(f"   {error}")
        print()

    # Print orchestrator roles
    orchestrators_dir = agents_dir / ORCHESTRATORS_SUBDIR
    print("📊 Orchestrators:")
    for orch_name in EXPECTED_ORCHESTRATORS:
        role = ORCHESTRATOR_ROLES.get(orch_name, "UNKNOWN")
        status = "✅" if (orchestrators_dir / orch_name / "main.py").exists() else "❌"
        print(f"   {status} {orch_name}: {role}")
    print()

    # Print specialist agent roles
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR
    print("📊 Specialists:")
    for agent_name in EXPECTED_AGENTS:
        role = AGENT_ROLES.get(agent_name, "UNKNOWN")
        status = "✅" if (specialists_dir / agent_name / "main.py").exists() else "❌"
        print(f"   {status} {agent_name}: {role}")
    print()

    total_agents = len(EXPECTED_ORCHESTRATORS) + len(EXPECTED_AGENTS)
    if all_valid:
        print("✅ All validations passed!")
        print(f"   {total_agents} agents ready for deployment (1 orchestrator + {len(EXPECTED_AGENTS)} specialists)")
        print("   Architecture: inventory_hub + 4 Specialists")
        return 0
    else:
        print(f"⚠️  Validation completed with {len(all_errors)} issue(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
