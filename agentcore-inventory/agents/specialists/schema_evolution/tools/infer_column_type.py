# =============================================================================
# Infer Column Type Tool
# =============================================================================
# Infers PostgreSQL type from sample data values.
# =============================================================================

import re
from typing import Dict, Any, List

from shared.xray_tracer import trace_tool_call


@trace_tool_call("sga_infer_column_type")
async def infer_column_type_tool(
    sample_values: List[str],
) -> Dict[str, Any]:
    """
    Infer PostgreSQL type from sample data.

    Uses conservative inference - prefers TEXT for ambiguous cases
    to avoid data loss. Examines sample values to detect:
    - Integers (INTEGER or BIGINT based on magnitude)
    - Decimals (NUMERIC for currency/precision)
    - Booleans (true/false, 1/0, yes/no, sim/não)
    - Dates (ISO, BR, US formats)
    - Text (VARCHAR based on length, or TEXT for long values)

    Args:
        sample_values: List of sample values from CSV column

    Returns:
        Dictionary with:
        - inferred_type: PostgreSQL data type string
        - reasoning: Why this type was chosen
        - sample_count: Number of samples analyzed
    """
    if not sample_values:
        return {
            "inferred_type": "TEXT",
            "reasoning": "Sem valores de amostra",
            "sample_count": 0,
        }

    # Filter empty values
    non_empty = [v.strip() for v in sample_values if v and v.strip()]
    if not non_empty:
        return {
            "inferred_type": "TEXT",
            "reasoning": "Todos os valores estão vazios",
            "sample_count": 0,
        }

    # Check for integers
    def is_integer(v):
        try:
            cleaned = v.replace(",", "").replace(".", "").strip()
            int(cleaned)
            return "." not in v or v.count(".") == v.count(",")
        except (ValueError, AttributeError):
            return False

    if all(is_integer(v) for v in non_empty):
        try:
            max_val = max(abs(int(v.replace(",", "").replace(".", "")))
                         for v in non_empty)
            if max_val > 2147483647:
                return {
                    "inferred_type": "BIGINT",
                    "reasoning": f"Inteiros grandes (max: {max_val})",
                    "sample_count": len(non_empty),
                }
            return {
                "inferred_type": "INTEGER",
                "reasoning": "Valores inteiros",
                "sample_count": len(non_empty),
            }
        except ValueError:
            return {
                "inferred_type": "INTEGER",
                "reasoning": "Valores inteiros",
                "sample_count": len(non_empty),
            }

    # Check for decimals
    def is_decimal(v):
        try:
            cleaned = v.replace(" ", "")
            if "," in cleaned and "." in cleaned:
                if cleaned.index(",") > cleaned.index("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            float(cleaned)
            return True
        except (ValueError, AttributeError):
            return False

    if all(is_decimal(v) for v in non_empty):
        return {
            "inferred_type": "NUMERIC(12,2)",
            "reasoning": "Valores decimais/moeda",
            "sample_count": len(non_empty),
        }

    # Check for booleans
    bool_values = {'true', 'false', '1', '0', 'yes', 'no', 'sim', 'não', 'nao'}
    if all(v.lower() in bool_values for v in non_empty):
        return {
            "inferred_type": "BOOLEAN",
            "reasoning": "Valores booleanos",
            "sample_count": len(non_empty),
        }

    # Check for dates
    date_patterns = [
        r'^\d{4}-\d{2}-\d{2}',      # ISO: 2024-01-15
        r'^\d{2}/\d{2}/\d{4}',      # BR/US: 15/01/2024
        r'^\d{2}-\d{2}-\d{4}',      # Alt: 15-01-2024
        r'^\d{4}/\d{2}/\d{2}',      # Alt: 2024/01/15
        r'^\d{2}\.\d{2}\.\d{4}',    # European: 15.01.2024
    ]

    def is_date(v):
        return any(re.match(p, v.strip()) for p in date_patterns)

    if all(is_date(v) for v in non_empty):
        return {
            "inferred_type": "TIMESTAMPTZ",
            "reasoning": "Valores de data",
            "sample_count": len(non_empty),
        }

    # Default: Text with length consideration
    max_len = max(len(v) for v in non_empty)
    if max_len <= 100:
        return {
            "inferred_type": "VARCHAR(100)",
            "reasoning": f"Texto curto (max {max_len} chars)",
            "sample_count": len(non_empty),
        }
    elif max_len <= 255:
        return {
            "inferred_type": "VARCHAR(255)",
            "reasoning": f"Texto médio (max {max_len} chars)",
            "sample_count": len(non_empty),
        }
    elif max_len <= 500:
        return {
            "inferred_type": "VARCHAR(500)",
            "reasoning": f"Texto longo (max {max_len} chars)",
            "sample_count": len(non_empty),
        }

    return {
        "inferred_type": "TEXT",
        "reasoning": f"Texto muito longo (max {max_len} chars)",
        "sample_count": len(non_empty),
    }
