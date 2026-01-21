# =============================================================================
# Debug Analytics Module for SGA
# =============================================================================
# Created for BUG-027: Debug Agent Validation & Enhancement
#
# Multi-destination analytics for Debug Agent user actions:
# 1. CloudWatch Metrics - Real-time dashboards
# 2. DynamoDB - Queryable, long-term storage
# 3. AgentCore Observability - Unified trace view (via context)
#
# Interview Decisions Applied:
# - Track ALL user actions on DebugAnalysisPanel
# - Store escalations for batch review
# - Use AgentCore Memory 360-day STM cycle
#
# Usage:
#     from shared.debug_analytics import DebugAnalytics
#
#     analytics = DebugAnalytics()
#     await analytics.record_action(
#         action="retry",
#         error_signature="sig_abc123",
#         error_type="ValidationError",
#         suggested_action="retry",
#         user_id="user@example.com",
#         session_id="sess_xyz",
#     )
# =============================================================================

import logging
import os
import time
from datetime import datetime, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Types
# =============================================================================

DebugAction = Literal["retry", "fallback", "escalate", "abort"]
ResolutionStatus = Literal["pending", "resolved", "escalated"]


# =============================================================================
# Analytics Class
# =============================================================================


class DebugAnalytics:
    """
    Multi-destination analytics for Debug Agent user actions.

    Emits to:
    - CloudWatch Metrics (real-time dashboards)
    - DynamoDB (queryable, long-term storage)

    Thread-safe and lazy-loads AWS clients.
    """

    def __init__(
        self,
        cloudwatch_namespace: str = "FaistonOne/DebugAgent",
        analytics_table_name: Optional[str] = None,
        escalation_table_name: Optional[str] = None,
        emit_to_cloudwatch: bool = True,
        emit_to_dynamodb: bool = True,
    ):
        """
        Initialize DebugAnalytics.

        Args:
            cloudwatch_namespace: CloudWatch namespace for metrics
            analytics_table_name: DynamoDB table for analytics (auto-detected if None)
            escalation_table_name: DynamoDB table for escalations (auto-detected if None)
            emit_to_cloudwatch: Whether to emit to CloudWatch
            emit_to_dynamodb: Whether to emit to DynamoDB
        """
        self.cloudwatch_namespace = cloudwatch_namespace
        self.emit_to_cloudwatch = emit_to_cloudwatch
        self.emit_to_dynamodb = emit_to_dynamodb

        # Auto-detect table names from environment
        env = os.environ.get("ENVIRONMENT", "prod")
        project = os.environ.get("PROJECT_NAME", "faiston-one")

        self.analytics_table = analytics_table_name or f"{project}-sga-debug-analytics-{env}"
        self.escalation_table = escalation_table_name or f"{project}-sga-escalation-log-{env}"

        # Lazy-loaded clients
        self._cloudwatch_client = None
        self._dynamodb_client = None

    def _get_cloudwatch_client(self):
        """Lazy load CloudWatch client."""
        if self._cloudwatch_client is None and self.emit_to_cloudwatch:
            try:
                import boto3

                self._cloudwatch_client = boto3.client("cloudwatch", region_name="us-east-2")
            except Exception as e:
                logger.warning(f"[DebugAnalytics] Failed to create CloudWatch client: {e}")
        return self._cloudwatch_client

    def _get_dynamodb_client(self):
        """Lazy load DynamoDB resource."""
        if self._dynamodb_client is None and self.emit_to_dynamodb:
            try:
                import boto3

                self._dynamodb_client = boto3.resource("dynamodb", region_name="us-east-2")
            except Exception as e:
                logger.warning(f"[DebugAnalytics] Failed to create DynamoDB client: {e}")
        return self._dynamodb_client

    def _emit_cloudwatch_metric(
        self,
        action: DebugAction,
        error_type: str,
        suggested_action: DebugAction,
        user_chose_different: bool,
    ) -> None:
        """Emit CloudWatch metric for Debug Agent user action."""
        client = self._get_cloudwatch_client()
        if not client:
            logger.debug(
                f"[DebugAnalytics] CloudWatch disabled: action={action}, error_type={error_type}"
            )
            return

        try:
            client.put_metric_data(
                Namespace=self.cloudwatch_namespace,
                MetricData=[
                    {
                        "MetricName": "UserAction",
                        "Dimensions": [
                            {"Name": "Action", "Value": action},
                            {"Name": "ErrorType", "Value": error_type},
                            {"Name": "UserChoseDifferent", "Value": str(user_chose_different)},
                        ],
                        "Value": 1,
                        "Unit": "Count",
                    },
                    {
                        "MetricName": f"Action_{action}",
                        "Value": 1,
                        "Unit": "Count",
                    },
                ],
            )
            logger.debug(f"[DebugAnalytics] CloudWatch metric emitted: action={action}")
        except Exception as e:
            logger.warning(f"[DebugAnalytics] Failed to emit CloudWatch metric: {e}")

    def _write_analytics_record(
        self,
        action: DebugAction,
        error_signature: str,
        error_type: str,
        suggested_action: DebugAction,
        user_chose_different: bool,
        resolution_status: ResolutionStatus,
        session_id: str,
        user_id: str,
        timestamp: str,
    ) -> None:
        """Write analytics record to DynamoDB."""
        dynamodb = self._get_dynamodb_client()
        if not dynamodb:
            logger.debug(f"[DebugAnalytics] DynamoDB disabled: action={action}")
            return

        try:
            table = dynamodb.Table(self.analytics_table)

            # Extract date for partition key
            date_str = timestamp[:10]  # YYYY-MM-DD

            # Calculate TTL (1 year from now)
            ttl = int(time.time()) + (365 * 24 * 60 * 60)

            item = {
                "PK": f"DEBUG#{date_str}",
                "SK": f"ACTION#{timestamp}#{session_id}",
                "action": action,
                "error_signature": error_signature,
                "error_type": error_type,
                "suggested_action": suggested_action,
                "user_chose_different": user_chose_different,
                "resolution_status": resolution_status,
                "session_id": session_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "TTL": ttl,
                # GSI keys
                "GSI1PK": f"ERROR#{error_signature}",
                "GSI1SK": timestamp,
                "GSI2PK": f"USER#{user_id}",
                "GSI2SK": timestamp,
                "GSI3PK": f"ACTION#{action}",
                "GSI3SK": timestamp,
            }

            table.put_item(Item=item)
            logger.debug(f"[DebugAnalytics] DynamoDB record written: action={action}")
        except Exception as e:
            logger.warning(f"[DebugAnalytics] Failed to write DynamoDB record: {e}")

    def _write_escalation_record(
        self,
        error_signature: str,
        error_type: str,
        debug_analysis: dict,
        user_id: str,
        session_id: str,
        timestamp: str,
    ) -> None:
        """Write escalation record to DynamoDB."""
        dynamodb = self._get_dynamodb_client()
        if not dynamodb:
            logger.debug(f"[DebugAnalytics] DynamoDB disabled: escalation skipped")
            return

        try:
            table = dynamodb.Table(self.escalation_table)

            # Extract date for partition key
            date_str = timestamp[:10]  # YYYY-MM-DD

            # Calculate TTL (2 years from now)
            ttl = int(time.time()) + (2 * 365 * 24 * 60 * 60)

            item = {
                "PK": f"ESCALATION#{date_str}",
                "SK": f"ERROR#{timestamp}#{session_id}",
                "error_signature": error_signature,
                "error_type": error_type,
                "debug_analysis": debug_analysis,
                "user_id": user_id,
                "session_id": session_id,
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "resolution_notes": None,
                "created_at": timestamp,
                "TTL": ttl,
                # GSI keys
                "GSI1PK": "STATUS#pending",
                "GSI1SK": timestamp,
                "GSI2PK": f"ERROR#{error_signature}",
                "GSI2SK": timestamp,
                "GSI3PK": f"USER#{user_id}",
                "GSI3SK": timestamp,
            }

            table.put_item(Item=item)
            logger.info(f"[DebugAnalytics] Escalation logged: error_signature={error_signature}")
        except Exception as e:
            logger.warning(f"[DebugAnalytics] Failed to write escalation record: {e}")

    def record_action(
        self,
        action: DebugAction,
        error_signature: str,
        error_type: str,
        suggested_action: DebugAction,
        user_id: str,
        session_id: str,
        debug_analysis: Optional[dict] = None,
        resolution_status: ResolutionStatus = "pending",
    ) -> None:
        """
        Record a user action on DebugAnalysisPanel.

        Emits to CloudWatch and DynamoDB for comprehensive tracking.

        Args:
            action: User's chosen action (retry, fallback, escalate, abort)
            error_signature: Unique error identifier from Debug Agent
            error_type: Error classification from Debug Agent
            suggested_action: What Debug Agent recommended
            user_id: Cognito user ID
            session_id: Browser session ID
            debug_analysis: Full Debug Agent analysis (required for escalate)
            resolution_status: Current status of the error
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        user_chose_different = action != suggested_action

        logger.info(
            f"[DebugAnalytics] Recording action: {action} "
            f"(suggested={suggested_action}, different={user_chose_different})"
        )

        # Emit CloudWatch metric
        self._emit_cloudwatch_metric(
            action=action,
            error_type=error_type,
            suggested_action=suggested_action,
            user_chose_different=user_chose_different,
        )

        # Write analytics record
        self._write_analytics_record(
            action=action,
            error_signature=error_signature,
            error_type=error_type,
            suggested_action=suggested_action,
            user_chose_different=user_chose_different,
            resolution_status="escalated" if action == "escalate" else resolution_status,
            session_id=session_id,
            user_id=user_id,
            timestamp=timestamp,
        )

        # Write escalation record if user chose to escalate
        if action == "escalate" and debug_analysis:
            self._write_escalation_record(
                error_signature=error_signature,
                error_type=error_type,
                debug_analysis=debug_analysis,
                user_id=user_id,
                session_id=session_id,
                timestamp=timestamp,
            )


# =============================================================================
# Module-level instance for convenience
# =============================================================================

_default_analytics: Optional[DebugAnalytics] = None


def get_debug_analytics() -> DebugAnalytics:
    """Get the default DebugAnalytics instance."""
    global _default_analytics
    if _default_analytics is None:
        _default_analytics = DebugAnalytics()
    return _default_analytics


def record_debug_action(
    action: DebugAction,
    error_signature: str,
    error_type: str,
    suggested_action: DebugAction,
    user_id: str,
    session_id: str,
    debug_analysis: Optional[dict] = None,
) -> None:
    """
    Convenience function to record a debug action.

    Usage:
        from shared.debug_analytics import record_debug_action

        record_debug_action(
            action="retry",
            error_signature="sig_abc123",
            error_type="ValidationError",
            suggested_action="retry",
            user_id="user@example.com",
            session_id="sess_xyz",
        )
    """
    get_debug_analytics().record_action(
        action=action,
        error_signature=error_signature,
        error_type=error_type,
        suggested_action=suggested_action,
        user_id=user_id,
        session_id=session_id,
        debug_analysis=debug_analysis,
    )
