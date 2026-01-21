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
# =============================================================================

import sys
from pathlib import Path
from typing import List, Tuple

# Directory structure (ADR-002)
SPECIALISTS_SUBDIR = "specialists"
ORCHESTRATORS_SUBDIR = "orchestrators"

# Expected specialist agents (10 INVENTORY agents)
# NOTE: "data_import" because "import" is a Python reserved keyword (SyntaxError)
# NOTE: carrier, expedition, reverse, reconciliacao belong to agentcore-carrier project
EXPECTED_AGENTS = [
    "compliance",
    "data_import",  # Renamed from "import" - Python reserved word
    # AUDIT-004/2: equipment_research removed - dead code replaced by enrichment agent
    "estoque_control",
    "file_analyzer",  # BUG-025: CSV/XLSX analysis with Pydantic structured output
    "intake",
    "learning",
    "nexo_import",
    "observation",
    "schema_evolution",
    "validation",
    "vision_analyzer",  # BUG-025: Vision document analysis
]

# Agent roles for documentation (10 INVENTORY agents)
# NOTE: "data_import" renamed from "import" (Python reserved keyword)
# NOTE: carrier, expedition, reverse, reconciliacao belong to agentcore-carrier project
AGENT_ROLES = {
    "nexo_import": "ORCHESTRATOR",
    "intake": "SPECIALIST (NF Parsing)",
    "data_import": "SPECIALIST (Spreadsheet)",  # Renamed from "import"
    "estoque_control": "SPECIALIST (Inventory Control)",
    "learning": "SPECIALIST (Memory/Learning)",
    "observation": "SUPPORT (Audit Trail)",
    "validation": "SUPPORT (Validation)",
    "compliance": "SUPPORT (Compliance)",
    # AUDIT-004/2: equipment_research removed - dead code replaced by enrichment agent
    "schema_evolution": "SUPPORT (Schema Evolution)",
    "file_analyzer": "SPECIALIST (File Analysis)",  # BUG-025
    "vision_analyzer": "SPECIALIST (Vision Analysis)",  # BUG-025
}

# Required files for each agent subdirectory
# NOTE: agent.py REMOVED - legacy Google ADK format. Now using Strands A2A via main.py only.
# NOTE: Dockerfile REMOVED - ADR-001 mandates ZIP deploy with AgentCore, not Docker.
REQUIRED_FILES = [
    "__init__.py",
    "main.py",  # Strands A2AServer entry point (replaced agent.py)
    "requirements.txt",
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

        # Check tools directory
        tools_dir = agent_dir / "tools"
        if not tools_dir.exists():
            errors.append(f"❌ {agent_name}: Missing tools/ directory")
        else:
            # Check tools __init__.py
            tools_init = tools_dir / "__init__.py"
            if not tools_init.exists():
                errors.append(f"❌ {agent_name}: Missing tools/__init__.py")

            # Check at least one tool file exists
            tool_files = [f for f in tools_dir.glob("*.py") if f.name != "__init__.py"]
            if not tool_files:
                errors.append(f"⚠️  {agent_name}: No tool files in tools/")

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

        # Check for A2AServer
        if "A2AServer" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing A2AServer")

        # Check for @tool decorator
        if "@tool" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing @tool decorators")

        # Check for port 9000
        if "9000" not in content:
            errors.append(f"⚠️  {agent_name}: main.py not using port 9000")

        # Check for serve_at_root
        if "serve_at_root" not in content:
            errors.append(f"⚠️  {agent_name}: main.py missing serve_at_root=True")

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

            # Check create_agent function exists
            if "def create_agent" not in content:
                errors.append(f"⚠️  {agent_name}: main.py missing create_agent function")

            # Check main() function exists
            if "def main()" not in content:
                errors.append(f"⚠️  {agent_name}: main.py missing main() function")

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

    return len(errors) == 0, errors


def main():
    """Run all validations."""
    print("=" * 60)
    print("🔍 Agent Structure Validation (TRUE Multi-Agent A2A)")
    print("=" * 60)
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

    # 2. Validate agent structure
    print("📁 Checking agent directory structure...")
    valid, errors = validate_agent_structure(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ All agents present' if valid else '❌ Issues found'}")

    # 3. Validate shared module
    print("📦 Checking shared module...")
    valid, errors = validate_shared_module(base_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ Shared module complete' if valid else '❌ Issues found'}")

    # 4. Validate per-agent main.py (Strands A2AServer)
    print("🚀 Checking per-agent main.py (Strands A2AServer)...")
    valid, errors = validate_per_agent_main(agents_dir)
    all_valid = all_valid and valid
    all_errors.extend(errors)
    print(f"   {'✅ All main.py files valid' if valid else '❌ Issues found'}")

    # 5. Dockerfiles - SKIPPED per ADR-001 (ZIP deploy, not Docker)
    print("🐳 Dockerfiles: SKIPPED (ADR-001: ZIP deploy)")

    # 6. Validate agent content
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

    # Print agent roles
    specialists_dir = agents_dir / SPECIALISTS_SUBDIR
    print("📊 Agent Roles:")
    for agent_name in EXPECTED_AGENTS:
        role = AGENT_ROLES.get(agent_name, "UNKNOWN")
        status = "✅" if (specialists_dir / agent_name / "main.py").exists() else "❌"
        print(f"   {status} {agent_name}: {role}")
    print()

    if all_valid:
        print("✅ All validations passed!")
        print(f"   {len(EXPECTED_AGENTS)} agents ready for deployment")
        print("   Architecture: TRUE Multi-Agent A2A (ORCHESTRATOR + SPECIALISTS)")
        return 0
    else:
        print(f"⚠️  Validation completed with {len(all_errors)} issue(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
