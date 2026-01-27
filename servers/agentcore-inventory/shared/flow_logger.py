"""
PII-Safe Smart Import Flow Logger

CRITICAL SAFETY CONSTRAINTS:
- NEVER log file content, column names, or cell values
- ONLY log safe references: session_id, job_id, s3_key, counts, durations, confidence scores
- Count-only pattern enforced across all log points

Usage:
    from shared.flow_logger import flow_log

    # Method 1: Context manager (auto-timing)
    with flow_log.phase_context(3, "SchemaMapper", session_id, source_columns_count=10):
        # Your phase logic here
        pass

    # Method 2: Manual logging
    flow_log.phase_start(2, "InventoryAnalyst", session_id)
    # ... logic ...
    flow_log.phase_end(2, "InventoryAnalyst", session_id, "SUCCESS", duration_ms=1234)

    # Method 3: Decision points
    flow_log.decision(
        "Questions generated for HIL",
        session_id=session_id,
        questions_count=2,
        status="NEEDS_INPUT"
    )
"""

import structlog
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any

logger = structlog.get_logger()


class SmartImportLogger:
    """
    PII-safe logging for Smart Import flow.

    CRITICAL: Uses count-only pattern - NEVER logs content, column names, or values.
    Safe to log: session_id, job_id, s3_key, counts, durations, confidence scores, status codes.
    """

    @staticmethod
    def phase_start(phase: int, name: str, session_id: str, **kwargs):
        """
        Log the start of a Smart Import phase.

        Args:
            phase: Phase number (1-5)
            name: Agent name (e.g., "SchemaMapper", "DataTransformer")
            session_id: Import session identifier
            **kwargs: Additional PII-safe metrics (counts, flags, etc.)
        """
        logger.info(
            f"Phase {phase} START: {name}",
            phase=phase,
            agent=name,
            session_id=session_id,
            event_type="phase_start",
            **kwargs
        )

    @staticmethod
    def phase_end(
        phase: int,
        name: str,
        session_id: str,
        status: str,
        duration_ms: int,
        **kwargs
    ):
        """
        Log the end of a Smart Import phase.

        Args:
            phase: Phase number (1-5)
            name: Agent name
            session_id: Import session identifier
            status: "SUCCESS" | "FAILED" | "PARTIAL"
            duration_ms: Execution time in milliseconds
            **kwargs: Additional PII-safe metrics
        """
        logger.info(
            f"Phase {phase} END: {name} {status}",
            phase=phase,
            agent=name,
            session_id=session_id,
            status=status,
            duration_ms=duration_ms,
            event_type="phase_end",
            **kwargs
        )

    @staticmethod
    def decision(description: str, session_id: str, **kwargs):
        """
        Log a key decision or milestone within a phase.

        Use for:
        - questions_count verification
        - Mapping proposals (mappings_count, confidence)
        - Transform progress (rows_processed, rows_rejected)
        - Pattern detection (insights_count, severity)

        Args:
            description: Human-readable description of the decision
            session_id: Import session identifier
            **kwargs: PII-safe metrics (counts, scores, flags)

        Example:
            flow_log.decision(
                "Questions generated for HIL",
                session_id="nexo_123",
                questions_count=2,
                status="NEEDS_INPUT"
            )
        """
        logger.info(
            f"DECISION: {description}",
            session_id=session_id,
            event_type="decision",
            **kwargs
        )

    @contextmanager
    def phase_context(self, phase: int, name: str, session_id: str, **kwargs):
        """
        Context manager for automatic phase timing and error handling.

        Usage:
            with flow_log.phase_context(3, "SchemaMapper", session_id, source_columns_count=10):
                # Phase logic here
                response = schema_mapper_agent.invoke(...)

        Benefits:
        - Automatic phase_start/phase_end logging
        - Automatic duration calculation
        - Exception logging (errors still propagate to @cognitive_error_handler)

        Args:
            phase: Phase number (1-5)
            name: Agent name
            session_id: Import session identifier
            **kwargs: Additional PII-safe context metrics
        """
        start = time.time()
        try:
            self.phase_start(phase, name, session_id, **kwargs)
            yield
            duration_ms = int((time.time() - start) * 1000)
            self.phase_end(phase, name, session_id, "SUCCESS", duration_ms)
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.error(
                f"Phase {phase} FAILED: {name}",
                phase=phase,
                agent=name,
                session_id=session_id,
                error_type=type(e).__name__,
                duration_ms=duration_ms,
                event_type="phase_error",
                exc_info=True  # Include stack trace
            )
            # Error routing handled by @cognitive_error_handler or DebugHook
            # Re-raise to preserve error propagation
            raise


# Global singleton instance
flow_log = SmartImportLogger()
