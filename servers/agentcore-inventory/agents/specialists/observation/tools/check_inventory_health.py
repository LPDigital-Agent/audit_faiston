# =============================================================================
# ObservationAgent Tool: Check Inventory Health
# =============================================================================
# Queries the inventory database for anomalies and health metrics.
# All queries are ACTOR-SCOPED with WHERE owner_id = :actor_id.
#
# HEALTH CHECKS:
# 1. Zero Stock Items (30+ days unchanged)
# 2. Duplicate Part Numbers
# 3. Missing Required Fields
# 4. Price Anomalies (>3 std dev from mean)
# 5. Stale Sessions (pending > 7 days)
#
# VERSION: 2026-01-22T00:00:00Z
# =============================================================================

import json
import logging
from typing import Dict, Any, List, Optional

from strands import tool

from shared.cognitive_error_handler import cognitive_error_handler
from shared.debug_utils import debug_error

logger = logging.getLogger(__name__)


# =============================================================================
# Health Check SQL Queries (Actor-Scoped)
# =============================================================================

# CRITICAL: ALL queries MUST include WHERE owner_id = %(actor_id)s
# No cross-tenant data mixing allowed (per CLAUDE.md)

HEALTH_QUERIES = {
    "zero_stock": {
        "description": "Items with zero quantity for 30+ days",
        "severity": "warning",
        "query": """
            SELECT
                part_number,
                description,
                quantity_total,
                updated_at
            FROM sga.mv_inventory_summary
            WHERE owner_id = %(actor_id)s
              AND quantity_total = 0
              AND updated_at < NOW() - INTERVAL '30 days'
            ORDER BY updated_at ASC
            LIMIT 50
        """,
    },
    "duplicates": {
        "description": "Duplicate part numbers",
        "severity": "critical",
        "query": """
            SELECT
                part_number,
                COUNT(*) as occurrence_count
            FROM sga.pending_entry_items
            WHERE owner_id = %(actor_id)s
              AND status = 'pending'
            GROUP BY part_number
            HAVING COUNT(*) > 1
            ORDER BY occurrence_count DESC
            LIMIT 50
        """,
    },
    "missing_required": {
        "description": "Items missing required fields",
        "severity": "warning",
        "query": """
            SELECT
                id,
                part_number,
                description,
                created_at
            FROM sga.pending_entry_items
            WHERE owner_id = %(actor_id)s
              AND (
                  part_number IS NULL
                  OR part_number = ''
                  OR description IS NULL
                  OR description = ''
              )
            ORDER BY created_at DESC
            LIMIT 50
        """,
    },
    "price_anomalies": {
        "description": "Items with price > 3 standard deviations from mean",
        "severity": "warning",
        "query": """
            WITH price_stats AS (
                SELECT
                    AVG(unit_price) as avg_price,
                    STDDEV(unit_price) as std_price
                FROM sga.pending_entry_items
                WHERE owner_id = %(actor_id)s
                  AND unit_price IS NOT NULL
                  AND unit_price > 0
            )
            SELECT
                pei.part_number,
                pei.description,
                pei.unit_price,
                ps.avg_price,
                ps.std_price,
                ABS(pei.unit_price - ps.avg_price) / NULLIF(ps.std_price, 0) as z_score
            FROM sga.pending_entry_items pei
            CROSS JOIN price_stats ps
            WHERE pei.owner_id = %(actor_id)s
              AND pei.unit_price IS NOT NULL
              AND ps.std_price > 0
              AND ABS(pei.unit_price - ps.avg_price) > (3 * ps.std_price)
            ORDER BY z_score DESC
            LIMIT 20
        """,
    },
    "stale_sessions": {
        "description": "Pending sessions older than 7 days",
        "severity": "info",
        "query": """
            SELECT
                session_id,
                COUNT(*) as item_count,
                MIN(created_at) as oldest_item,
                MAX(created_at) as newest_item
            FROM sga.pending_entry_items
            WHERE owner_id = %(actor_id)s
              AND status = 'pending'
              AND created_at < NOW() - INTERVAL '7 days'
            GROUP BY session_id
            ORDER BY oldest_item ASC
            LIMIT 20
        """,
    },
    "negative_quantities": {
        "description": "Items with negative quantity values",
        "severity": "critical",
        "query": """
            SELECT
                part_number,
                description,
                quantity
            FROM sga.pending_entry_items
            WHERE owner_id = %(actor_id)s
              AND quantity < 0
            ORDER BY quantity ASC
            LIMIT 50
        """,
    },
}


# =============================================================================
# Health Score Calculation
# =============================================================================


def _calculate_health_score(anomaly_counts: Dict[str, int], total_items: int) -> float:
    """
    Calculate overall health score (0.0 - 1.0).

    Weights:
    - Critical issues (duplicates, negative quantities): -0.3 per occurrence (capped at -0.6)
    - Warning issues (zero stock, missing fields, price anomalies): -0.05 per occurrence (capped at -0.3)
    - Info issues (stale sessions): -0.01 per occurrence (capped at -0.1)

    Base score is 1.0, reduced by penalties.
    """
    if total_items == 0:
        return 1.0  # No data = healthy (new user)

    score = 1.0

    # Critical penalties
    critical_count = anomaly_counts.get("duplicates", 0) + anomaly_counts.get("negative_quantities", 0)
    critical_penalty = min(0.6, critical_count * 0.3)
    score -= critical_penalty

    # Warning penalties
    warning_count = (
        anomaly_counts.get("zero_stock", 0) +
        anomaly_counts.get("missing_required", 0) +
        anomaly_counts.get("price_anomalies", 0)
    )
    warning_penalty = min(0.3, warning_count * 0.05)
    score -= warning_penalty

    # Info penalties
    info_count = anomaly_counts.get("stale_sessions", 0)
    info_penalty = min(0.1, info_count * 0.01)
    score -= info_penalty

    return max(0.0, round(score, 2))


def _get_severity_emoji(severity: str) -> str:
    """Get emoji for severity level."""
    return {
        "critical": "🔴",
        "warning": "⚠️",
        "info": "ℹ️",
    }.get(severity, "")


# =============================================================================
# Tool Implementation
# =============================================================================


@tool
@cognitive_error_handler("observation")
def check_inventory_health(actor_id: str) -> str:
    """
    Check inventory database health for anomalies.

    Runs a series of health checks against the inventory database:
    1. Zero Stock Items: Items with quantity=0 for 30+ days
    2. Duplicate Part Numbers: Same part_number appearing multiple times
    3. Missing Required Fields: Items without part_number or description
    4. Price Anomalies: Prices > 3 standard deviations from mean
    5. Stale Sessions: Pending items older than 7 days
    6. Negative Quantities: Items with negative quantity values

    All queries are ACTOR-SCOPED: enforced with WHERE owner_id = :actor_id.
    No cross-tenant data mixing is allowed.

    Args:
        actor_id: User identifier for scoping queries.

    Returns:
        JSON string with health metrics:
        {
            "success": true,
            "actor_id": "user-123",
            "health_score": 0.85,
            "health_status": "good",
            "anomaly_counts": {
                "zero_stock": 5,
                "duplicates": 2,
                "missing_required": 0,
                "price_anomalies": 1,
                "stale_sessions": 3,
                "negative_quantities": 0
            },
            "anomaly_samples": {
                "duplicates": [{"part_number": "ABC123", "occurrence_count": 3}, ...]
            },
            "recommendations": [
                {"severity": "critical", "message": "Resolva 2 part numbers duplicados."},
                ...
            ],
            "human_message": "Saúde do inventário: 85% (bom). 2 problemas críticos detectados."
        }

    Raises:
        Exception: If database connection fails (caught internally, returns JSON error response with DATABASE_ERROR type).
    """
    try:
        # Import postgres client
        from tools.postgres_client import SGAPostgresClient
        db = SGAPostgresClient()

        anomaly_counts: Dict[str, int] = {}
        anomaly_samples: Dict[str, List[Dict[str, Any]]] = {}
        recommendations: List[Dict[str, str]] = []

        # Execute each health check
        for check_name, config in HEALTH_QUERIES.items():
            try:
                query = config["query"]
                results = db._execute_query(query, {"actor_id": actor_id})

                count = len(results)
                anomaly_counts[check_name] = count

                # Keep samples for reporting (limit to 5)
                if count > 0:
                    anomaly_samples[check_name] = results[:5]

                    # Generate recommendation
                    severity = config["severity"]
                    description = config["description"]
                    emoji = _get_severity_emoji(severity)

                    if check_name == "duplicates":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} part number(s) duplicado(s). Revise e corrija.",
                        })
                    elif check_name == "negative_quantities":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} item(ns) com quantidade negativa. Corrija imediatamente.",
                        })
                    elif check_name == "zero_stock":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} item(ns) com estoque zero há 30+ dias. Considere remover.",
                        })
                    elif check_name == "missing_required":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} item(ns) sem campos obrigatórios. Complete os dados.",
                        })
                    elif check_name == "price_anomalies":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} item(ns) com preço anômalo. Verifique se estão corretos.",
                        })
                    elif check_name == "stale_sessions":
                        recommendations.append({
                            "severity": severity,
                            "message": f"{emoji} {count} sessão(ões) pendente(s) há 7+ dias. Conclua ou cancele.",
                        })

                logger.info(
                    f"[check_inventory_health] {check_name}: {count} anomalies for actor={actor_id}"
                )

            except Exception as e:
                logger.warning(f"[check_inventory_health] {check_name} query failed: {e}")
                anomaly_counts[check_name] = 0

        # Get total item count for health score calculation
        try:
            total_query = """
                SELECT COUNT(*) as total
                FROM sga.pending_entry_items
                WHERE owner_id = %(actor_id)s
            """
            total_result = db._execute_query(total_query, {"actor_id": actor_id})
            total_items = total_result[0]["total"] if total_result else 0
        except Exception as e:
            logger.warning(f"[check_inventory_health] Total count query failed: {e}")
            total_items = 0

        # Calculate health score
        health_score = _calculate_health_score(anomaly_counts, total_items)

        # Determine health status
        if health_score >= 0.9:
            health_status = "excellent"
            health_status_pt = "excelente"
        elif health_score >= 0.7:
            health_status = "good"
            health_status_pt = "bom"
        elif health_score >= 0.5:
            health_status = "fair"
            health_status_pt = "regular"
        else:
            health_status = "poor"
            health_status_pt = "ruim"

        # Sort recommendations by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        recommendations.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 3))

        # Generate human message (pt-BR)
        critical_count = anomaly_counts.get("duplicates", 0) + anomaly_counts.get("negative_quantities", 0)
        total_anomalies = sum(anomaly_counts.values())

        if total_anomalies == 0:
            human_message = f"✅ Saúde do inventário: {int(health_score * 100)}% ({health_status_pt}). Nenhuma anomalia detectada!"
        elif critical_count > 0:
            human_message = (
                f"🔴 Saúde do inventário: {int(health_score * 100)}% ({health_status_pt}). "
                f"{critical_count} problema(s) crítico(s) requer(em) atenção imediata!"
            )
        else:
            human_message = (
                f"⚠️ Saúde do inventário: {int(health_score * 100)}% ({health_status_pt}). "
                f"{total_anomalies} anomalia(s) detectada(s)."
            )

        result = {
            "success": True,
            "actor_id": actor_id,
            "health_score": health_score,
            "health_status": health_status,
            "total_items": total_items,
            "anomaly_counts": anomaly_counts,
            "anomaly_samples": anomaly_samples,
            "recommendations": recommendations,
            "human_message": human_message,
        }

        logger.info(
            f"[check_inventory_health] Health check complete for actor={actor_id}: "
            f"score={health_score}, status={health_status}, anomalies={total_anomalies}"
        )

        return json.dumps(result)

    except Exception as e:
        # If database is not available, return graceful degradation
        logger.error(f"[check_inventory_health] Failed: {e}", exc_info=True)
        debug_error(e, "check_inventory_health", {"actor_id": actor_id})

        return json.dumps({
            "success": False,
            "error": str(e),
            "error_type": "DATABASE_ERROR",
            "actor_id": actor_id,
            "health_score": None,
            "health_status": "unknown",
            "anomaly_counts": {},
            "recommendations": [],
            "human_message": "Não foi possível verificar a saúde do inventário. Banco de dados indisponível.",
        })


# =============================================================================
# Module Exports
# =============================================================================

__all__ = ["check_inventory_health"]
