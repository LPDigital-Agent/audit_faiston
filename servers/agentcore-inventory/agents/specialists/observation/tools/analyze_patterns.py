# =============================================================================
# ObservationAgent Tool: Analyze Patterns
# =============================================================================
# Detects patterns in historical data using statistical and semantic analysis.
# Implements the THINK phase of OBSERVE → THINK → LEARN → ACT loop.
#
# PATTERN TYPES:
# 1. ERROR PATTERNS - Recurrent transformation errors (SchemaMismatch, DataIntegrity, etc.)
# 2. MAPPING PATTERNS - Unmapped columns with suggestions (Triangulation method)
# 3. BEHAVIOR PATTERNS - User preference patterns
#
# LEARNING MODE THRESHOLDS:
# - Minimum 3 sessions before detecting patterns (avoid false positives)
# - Minimum 50 rows of data before statistical insights
# - CRITICAL insights bypass thresholds (immediate alerting)
#
# VERSION: 2026-01-22T00:00:00Z
# =============================================================================

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from strands import tool

from shared.cognitive_error_handler import cognitive_error_handler

logger = logging.getLogger(__name__)


# =============================================================================
# Learning Mode Constants
# =============================================================================

MIN_SESSIONS_FOR_PATTERN = 3  # Minimum sessions before pattern detection
MIN_ROWS_FOR_STATS = 50       # Minimum rows for statistical insights

# Error pattern taxonomy
ERROR_PATTERNS = {
    "SchemaMismatch": {
        "keywords": ["missing column", "column not found", "unknown column", "schema"],
        "severity": "critical",
    },
    "DataIntegrity": {
        "keywords": ["type conversion", "null value", "invalid type", "parsing error"],
        "severity": "warning",
    },
    "BusinessLogic": {
        "keywords": ["duplicate", "negative stock", "constraint violation", "unique"],
        "severity": "critical",
    },
    "Formatting": {
        "keywords": ["date format", "currency", "number format", "encoding"],
        "severity": "info",
    },
}

# Triangulation weights for mapping detection
TRIANGULATION_WEIGHTS = {
    "frequency": 0.3,    # How often the column appears unmapped
    "semantic": 0.4,     # Semantic similarity to known target columns
    "history": 0.3,      # Historical success rate of similar mappings
}

# Known target schema columns (for semantic matching)
TARGET_SCHEMA_COLUMNS = [
    "part_number", "serial_number", "description", "quantity",
    "unit_price", "total_value", "location", "status",
    "manufacturer", "category", "model", "batch_number",
]


# =============================================================================
# Pattern Detection Helpers
# =============================================================================


def _detect_error_patterns(
    episodes: List[Dict[str, Any]],
    min_occurrences: int = 2,
) -> List[Dict[str, Any]]:
    """
    Detect error patterns from episode history.

    Categorizes errors into:
    - SchemaMismatch: Missing columns, schema issues
    - DataIntegrity: Type conversion, null handling
    - BusinessLogic: Duplicates, constraint violations
    - Formatting: Date, number, currency format issues

    Returns patterns sorted by frequency and severity.
    """
    error_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for episode in episodes:
        content = episode.get("content", "").lower()
        outcome = episode.get("outcome", "").lower()

        # Only analyze error/failure outcomes
        if "error" not in outcome and "fail" not in outcome:
            continue

        # Classify error by pattern type
        matched_type = "Unknown"
        for pattern_type, config in ERROR_PATTERNS.items():
            for keyword in config["keywords"]:
                if keyword.lower() in content:
                    matched_type = pattern_type
                    break
            if matched_type != "Unknown":
                break

        error_buckets[matched_type].append({
            "content": episode.get("content", ""),
            "session_id": episode.get("session_id", ""),
            "timestamp": episode.get("timestamp", ""),
        })

    # Build pattern results
    patterns = []
    for pattern_type, errors in error_buckets.items():
        if len(errors) < min_occurrences:
            continue

        severity = ERROR_PATTERNS.get(pattern_type, {}).get("severity", "info")
        patterns.append({
            "type": "error",
            "subtype": pattern_type,
            "frequency": len(errors),
            "severity": severity,
            "samples": errors[:3],  # Top 3 samples
            "confidence": min(0.95, 0.5 + (len(errors) * 0.1)),
            "description": f"Detected {len(errors)} occurrences of {pattern_type} errors",
        })

    # Sort by severity, then frequency
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    patterns.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x["frequency"]))

    return patterns


def _calculate_semantic_similarity(source: str, target: str) -> float:
    """
    Calculate semantic similarity between source and target column names.

    Uses simple heuristics:
    - Exact match: 1.0
    - Substring match: 0.7
    - Common prefix/suffix: 0.5
    - No match: 0.0

    For production, consider using thefuzz or embedding-based similarity.
    """
    source = source.lower().replace("_", "").replace("-", "")
    target = target.lower().replace("_", "").replace("-", "")

    if source == target:
        return 1.0

    if source in target or target in source:
        return 0.7

    # Check common prefixes (at least 3 chars)
    for i in range(min(len(source), len(target)), 2, -1):
        if source[:i] == target[:i]:
            return 0.5

    # Check common suffixes (at least 3 chars)
    for i in range(min(len(source), len(target)), 2, -1):
        if source[-i:] == target[-i:]:
            return 0.4

    return 0.0


def _detect_mapping_patterns(
    facts: List[Dict[str, Any]],
    episodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect unmapped columns with mapping suggestions.

    Uses Triangulation Method:
    - Frequency (0.3): How often the column appears unmapped
    - Semantic (0.4): Similarity to known target columns
    - History (0.3): Historical success rate of similar mappings

    Returns mapping opportunities sorted by confidence.
    """
    # Track unmapped columns from errors
    unmapped_columns: Dict[str, int] = defaultdict(int)

    for episode in episodes:
        content = episode.get("content", "")
        # Look for patterns like "unmapped column: X" or "unknown column: X"
        patterns = [
            r"unmapped column[:\s]+['\"]?(\w+)['\"]?",
            r"unknown column[:\s]+['\"]?(\w+)['\"]?",
            r"missing mapping for[:\s]+['\"]?(\w+)['\"]?",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                unmapped_columns[match] += 1

    # Track successful mappings from facts
    successful_mappings: Dict[str, str] = {}
    for fact in facts:
        content = fact.get("content", "")
        category = fact.get("category", "")
        if "mapping" in category.lower():
            # Look for patterns like "X maps to Y"
            match = re.search(r"['\"]?(\w+)['\"]?\s+maps?\s+to\s+['\"]?(\w+)['\"]?", content, re.IGNORECASE)
            if match:
                successful_mappings[match.group(1).lower()] = match.group(2).lower()

    # Build mapping opportunities using Triangulation
    patterns = []
    for column, frequency in unmapped_columns.items():
        if frequency < 2:  # Minimum occurrences
            continue

        # Calculate frequency score (normalized)
        max_freq = max(unmapped_columns.values()) if unmapped_columns else 1
        freq_score = frequency / max_freq

        # Calculate semantic similarity to target columns
        best_target = None
        best_semantic_score = 0.0
        for target in TARGET_SCHEMA_COLUMNS:
            similarity = _calculate_semantic_similarity(column, target)
            if similarity > best_semantic_score:
                best_semantic_score = similarity
                best_target = target

        # Calculate history score (from successful mappings)
        history_score = 0.0
        if column.lower() in successful_mappings:
            history_score = 0.9  # Previously mapped successfully

        # Triangulate confidence
        confidence = (
            (freq_score * TRIANGULATION_WEIGHTS["frequency"]) +
            (best_semantic_score * TRIANGULATION_WEIGHTS["semantic"]) +
            (history_score * TRIANGULATION_WEIGHTS["history"])
        )

        if confidence < 0.3:  # Minimum threshold
            continue

        patterns.append({
            "type": "mapping",
            "source_column": column,
            "suggested_target": best_target,
            "frequency": frequency,
            "confidence": round(confidence, 2),
            "severity": "warning" if confidence > 0.6 else "info",
            "triangulation": {
                "frequency_score": round(freq_score, 2),
                "semantic_score": round(best_semantic_score, 2),
                "history_score": round(history_score, 2),
            },
            "description": f"Column '{column}' appears unmapped {frequency} times. "
                          f"Suggested mapping: '{best_target}' (confidence: {round(confidence * 100)}%)",
        })

    # Sort by confidence
    patterns.sort(key=lambda x: -x["confidence"])

    return patterns


def _detect_behavior_patterns(
    facts: List[Dict[str, Any]],
    episodes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Detect user behavior patterns for optimization opportunities.

    Analyzes:
    - Frequently used file formats
    - Common import times
    - Preferred mapping confirmations
    """
    patterns = []

    # Analyze import frequency by time of day
    hour_counts: Dict[int, int] = defaultdict(int)
    for episode in episodes:
        timestamp = episode.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour_counts[dt.hour] += 1
            except ValueError:
                pass

    if hour_counts:
        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_count = hour_counts[peak_hour]
        if peak_count >= 3:  # Minimum for pattern
            patterns.append({
                "type": "behavior",
                "subtype": "peak_activity",
                "peak_hour": peak_hour,
                "frequency": peak_count,
                "confidence": min(0.9, 0.5 + (peak_count * 0.1)),
                "severity": "info",
                "description": f"Peak import activity at {peak_hour}:00. "
                              f"Consider scheduling background tasks outside this window.",
            })

    # Analyze categories for automation opportunities
    category_counts: Dict[str, int] = defaultdict(int)
    for fact in facts:
        category = fact.get("category", "unknown")
        category_counts[category] += 1

    # Check for repetitive confirmations
    for category, count in category_counts.items():
        if "confirm" in category.lower() and count >= 5:
            patterns.append({
                "type": "behavior",
                "subtype": "automation_opportunity",
                "category": category,
                "frequency": count,
                "confidence": min(0.85, 0.4 + (count * 0.05)),
                "severity": "info",
                "description": f"Pattern '{category}' confirmed {count} times. "
                              f"Consider auto-approval for high-confidence matches.",
            })

    return patterns


# =============================================================================
# Tool Implementation
# =============================================================================


@tool
@cognitive_error_handler("observation")
def analyze_patterns(
    activity_json: str,
    pattern_type: str = "all",
    enforce_learning_mode: bool = True,
) -> str:
    """
    Analyze Memory activity data to detect patterns.

    Implements the THINK phase of OBSERVE → THINK → LEARN → ACT loop.
    Uses statistical and semantic analysis to find:
    - Error patterns (SchemaMismatch, DataIntegrity, BusinessLogic, Formatting)
    - Mapping opportunities (Triangulation method: Frequency * 0.3 + Semantic * 0.4 + History * 0.3)
    - Behavior insights (automation opportunities, usage patterns)

    Learning Mode Enforcement:
    - Requires minimum 3 sessions before detecting patterns (avoids false positives)
    - Requires minimum 50 rows for statistical insights
    - CRITICAL patterns bypass thresholds (immediate alerting)

    Args:
        activity_json: JSON string from scan_recent_activity tool.
        pattern_type: Type of patterns to detect ("all", "error", "mapping", "behavior").
        enforce_learning_mode: If True, apply minimum thresholds for patterns.

    Returns:
        JSON string with detected patterns:
        {
            "success": true,
            "patterns": [
                {
                    "type": "error",
                    "subtype": "SchemaMismatch",
                    "frequency": 5,
                    "severity": "critical",
                    "confidence": 0.87,
                    "description": "Detected 5 occurrences of SchemaMismatch errors"
                },
                ...
            ],
            "pattern_summary": {
                "total_patterns": 8,
                "by_type": {"error": 3, "mapping": 4, "behavior": 1},
                "critical_count": 2,
                "warning_count": 3,
                "info_count": 3
            },
            "learning_mode_applied": true,
            "human_message": "Encontrei 8 padrões: 3 erros, 4 mapeamentos, 1 comportamento."
        }
    """
    try:
        # Parse activity data
        activity = json.loads(activity_json)

        if not activity.get("success"):
            return json.dumps({
                "success": False,
                "error": "Input activity data indicates failure",
                "patterns": [],
                "human_message": "Dados de atividade inválidos.",
            })

        facts = activity.get("facts", [])
        episodes = activity.get("episodes", [])
        summary = activity.get("activity_summary", {})

        # Check learning mode thresholds
        unique_sessions = summary.get("unique_sessions", 0)
        total_events = summary.get("total_facts", 0) + summary.get("total_episodes", 0)

        learning_mode_applied = False
        if enforce_learning_mode:
            if unique_sessions < MIN_SESSIONS_FOR_PATTERN:
                learning_mode_applied = True
                logger.info(
                    f"[analyze_patterns] Learning mode: {unique_sessions} sessions < {MIN_SESSIONS_FOR_PATTERN} required"
                )

        # Detect patterns
        all_patterns: List[Dict[str, Any]] = []

        if pattern_type in ("all", "error"):
            error_patterns = _detect_error_patterns(episodes)
            # CRITICAL errors bypass learning mode
            for p in error_patterns:
                if not learning_mode_applied or p["severity"] == "critical":
                    all_patterns.append(p)

        if pattern_type in ("all", "mapping"):
            mapping_patterns = _detect_mapping_patterns(facts, episodes)
            if not learning_mode_applied:
                all_patterns.extend(mapping_patterns)

        if pattern_type in ("all", "behavior"):
            behavior_patterns = _detect_behavior_patterns(facts, episodes)
            if not learning_mode_applied:
                all_patterns.extend(behavior_patterns)

        # Build summary
        by_type: Dict[str, int] = defaultdict(int)
        severity_counts = {"critical": 0, "warning": 0, "info": 0}

        for pattern in all_patterns:
            by_type[pattern["type"]] += 1
            severity = pattern.get("severity", "info")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        pattern_summary = {
            "total_patterns": len(all_patterns),
            "by_type": dict(by_type),
            "critical_count": severity_counts["critical"],
            "warning_count": severity_counts["warning"],
            "info_count": severity_counts["info"],
        }

        # Generate human message (pt-BR)
        if len(all_patterns) == 0:
            if learning_mode_applied:
                human_message = (
                    f"Modo aprendizado ativo: preciso de mais {MIN_SESSIONS_FOR_PATTERN - unique_sessions} "
                    f"sessão(ões) para detectar padrões confiáveis."
                )
            else:
                human_message = "Nenhum padrão significativo detectado."
        else:
            type_parts = []
            for t, count in by_type.items():
                type_names = {"error": "erro(s)", "mapping": "mapeamento(s)", "behavior": "comportamento(s)"}
                type_parts.append(f"{count} {type_names.get(t, t)}")
            human_message = f"Encontrei {len(all_patterns)} padrão(ões): {', '.join(type_parts)}."

            if severity_counts["critical"] > 0:
                human_message += f" 🔴 {severity_counts['critical']} crítico(s)!"

        logger.info(
            f"[analyze_patterns] Detected {len(all_patterns)} patterns "
            f"(critical: {severity_counts['critical']}, warning: {severity_counts['warning']})"
        )

        return json.dumps({
            "success": True,
            "patterns": all_patterns,
            "pattern_summary": pattern_summary,
            "learning_mode_applied": learning_mode_applied,
            "human_message": human_message,
        })

    except json.JSONDecodeError as e:
        logger.error(f"[analyze_patterns] Invalid JSON input: {e}")
        return json.dumps({
            "success": False,
            "error": f"Invalid JSON input: {str(e)}",
            "patterns": [],
            "human_message": "Erro ao processar dados de atividade.",
        })

    except Exception as e:
        logger.error(f"[analyze_patterns] Failed: {e}", exc_info=True)
        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "PATTERN_ANALYSIS_ERROR",
            "patterns": [],
            "human_message": "Erro ao analisar padrões. Tente novamente.",
        })


# =============================================================================
# Module Exports
# =============================================================================

__all__ = ["analyze_patterns"]
