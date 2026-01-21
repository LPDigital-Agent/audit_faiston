# =============================================================================
# Meta-Tooling - Self-Improvement Capabilities
# =============================================================================
# This module provides Meta-Tooling capabilities from strands_tools.
#
# Meta-Tooling allows agents to:
# - Create new tools at runtime (editor)
# - Load dynamically created tools (load_tool)
# - Execute shell commands for self-improvement (shell)
#
# Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/
# =============================================================================

import logging
from typing import List, Callable

logger = logging.getLogger(__name__)


def get_meta_tools() -> List[Callable]:
    """
    Get Meta-Tooling capabilities for agents.

    Returns:
        List of meta-tools: [load_tool, editor, shell]

    Note:
        These tools enable self-improvement but require careful use.
        Agents should only create tools when existing tools are insufficient.
    """
    try:
        from strands_tools import load_tool, editor, shell

        logger.info("[meta_tools] Loaded Meta-Tooling: load_tool, editor, shell")
        return [load_tool, editor, shell]

    except ImportError as e:
        logger.warning(
            "[meta_tools] strands_tools not available. Meta-Tooling disabled. "
            "Install with: pip install strands-agents[tools]. Error: %s",
            e,
        )
        # Return empty list - agents will work without Meta-Tooling
        return []


# =============================================================================
# Meta-Tooling Usage Examples (for agent reference)
# =============================================================================

META_TOOLING_EXAMPLES = """
## Meta-Tooling Usage Examples

### 1. Create a New Parser Tool

```python
# Agent encounters unknown file format
editor.write("parse_custom_format.py", '''
from strands import tool

@tool
def parse_custom_format(file_path: str) -> dict:
    \"\"\"Parse proprietary format from vendor XYZ.\"\"\"
    # Custom parsing logic
    with open(file_path, 'rb') as f:
        data = f.read()
    # Process data...
    return {"columns": [...], "data": [...]}
''')

# Load the new tool
load_tool("parse_custom_format")

# Now use it
result = parse_custom_format("/path/to/file.custom")
```

### 2. Create a Type Converter

```python
# Agent needs custom date format handling
editor.write("convert_brazilian_date.py", '''
from strands import tool
from datetime import datetime

@tool
def convert_brazilian_date(date_str: str) -> str:
    \"\"\"Convert DD/MM/YYYY to ISO format.\"\"\"
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.isoformat()
    except ValueError:
        return None
''')

load_tool("convert_brazilian_date")
```

### 3. Check System State

```python
# Agent needs to check database connectivity
result = shell("pg_isready -h localhost -p 5432")
if "accepting connections" in result:
    print("Database is ready")
```

## Safety Guidelines

1. **Only create tools when necessary** - First check if existing tools can handle the task
2. **Use descriptive names** - Tool names should clearly indicate purpose
3. **Include docstrings** - Help other agents understand the tool
4. **Test before use** - Use shell to verify tool works as expected
5. **Log tool creation** - Helps debugging and audit
"""
