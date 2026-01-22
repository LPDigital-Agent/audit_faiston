# =============================================================================
# Human-in-the-Loop (HIL) Workflow Manager
# =============================================================================
# Manages HIL approval tasks for critical inventory operations.
#
# Features:
# - Task creation with approval payloads
# - Task status management (pending, approved, rejected, expired)
# - Notification hooks for task assignment
# - Task execution after approval
#
# CRITICAL: Lazy imports for cold start optimization (<30s limit)
# =============================================================================

from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Lazy imports - DynamoDB client imported only when needed
_db_client = None


def _get_db_client():
    """
    Get DynamoDB client with lazy initialization.

    Returns:
        SGADynamoDBClient instance
    """
    global _db_client
    if _db_client is None:
        from tools.dynamodb_client import SGADynamoDBClient
        _db_client = SGADynamoDBClient()
    return _db_client


# =============================================================================
# HIL Task Types and Status
# =============================================================================


class HILTaskType:
    """Human-in-the-Loop task types."""
    APPROVAL_NEW_PN = "APPROVAL_NEW_PN"
    APPROVAL_ENTRY = "APPROVAL_ENTRY"
    APPROVAL_ADJUSTMENT = "APPROVAL_ADJUSTMENT"
    APPROVAL_DISCARD = "APPROVAL_DISCARD"
    APPROVAL_TRANSFER = "APPROVAL_TRANSFER"
    REVIEW_ENTRY = "REVIEW_ENTRY"
    ESCALATION = "ESCALATION"
    # Project Gate - For entries without project_id
    NEW_PROJECT_REQUEST = "NEW_PROJECT_REQUEST"


class HILTaskStatus:
    """HIL task status values."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    EXPIRED = "EXPIRED"


class HILTaskPriority:
    """HIL task priority levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


# =============================================================================
# HIL Workflow Manager
# =============================================================================


class HILWorkflowManager:
    """
    Manages Human-in-the-Loop workflow for inventory operations.

    Provides:
    - Task creation and assignment
    - Task status management
    - Approval/rejection processing
    - Post-approval action execution

    Example:
        manager = HILWorkflowManager()
        task = await manager.create_task(
            task_type=HILTaskType.APPROVAL_ADJUSTMENT,
            title="Aprovar ajuste de inventario",
            description="Ajuste de -5 unidades no PN XYZ",
            entity_type="MOVEMENT",
            entity_id="ADJ-20260104-abc123",
            requested_by="user@faiston.com",
            payload={"movement_item": {...}},
        )
    """

    def __init__(self):
        """Initialize the HIL Workflow Manager."""
        self._db = None

    @property
    def db(self):
        """Lazy-load DynamoDB client."""
        if self._db is None:
            self._db = _get_db_client()
        return self._db

    # =========================================================================
    # Task Creation
    # =========================================================================

    async def create_task(
        self,
        task_type: str,
        title: str,
        description: str,
        entity_type: str,
        entity_id: str,
        requested_by: str,
        payload: Optional[Dict[str, Any]] = None,
        priority: str = HILTaskPriority.MEDIUM,
        assigned_to: Optional[str] = None,
        assigned_role: Optional[str] = None,
        ttl_hours: int = 48,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new HIL task requiring human approval.

        Args:
            task_type: Type of approval task
            title: Short task title
            description: Detailed description (formatted message)
            entity_type: Type of entity being operated on
            entity_id: ID of the entity
            requested_by: User/agent who requested this action
            payload: Data to be processed after approval
            priority: Task priority
            assigned_to: Optional specific user assignment
            assigned_role: Optional role-based assignment
            ttl_hours: Task expiration in hours
            metadata: Additional metadata

        Returns:
            Created task dict with task_id
        """
        from agents.utils import EntityPrefix, generate_id, now_iso

        task_id = generate_id("TASK")
        now = now_iso()
        ttl_timestamp = int(datetime.utcnow().timestamp() + (ttl_hours * 3600))

        task_item = {
            "PK": f"{EntityPrefix.TASK}{task_id}",
            "SK": "METADATA",
            "entity_type": "HIL_TASK",
            "task_id": task_id,
            "task_type": task_type,
            "title": title,
            "description": description,
            "related_entity_type": entity_type,
            "related_entity_id": entity_id,
            "status": HILTaskStatus.PENDING,
            "priority": priority,
            "requested_by": requested_by,
            "assigned_to": assigned_to,
            "assigned_role": assigned_role or self._get_default_role(task_type),
            "payload": payload,
            "metadata": metadata or {},
            "created_at": now,
            "ttl": ttl_timestamp,
            # GSIs for HIL tasks table
            "GSI1_PK": f"TYPE#{task_type}",
            "GSI1_SK": f"{priority}#{now}",
            "GSI2_PK": f"STATUS#{HILTaskStatus.PENDING}",
            "GSI2_SK": now,
            "GSI3_PK": f"ASSIGNEE#{assigned_to or assigned_role or 'UNASSIGNED'}",
            "GSI3_SK": now,
            "GSI4_PK": f"ENTITY#{entity_type}#{entity_id}",
            "GSI4_SK": now,
        }

        # Save to HIL tasks table
        self.db.put_item(task_item, table_name=os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        ))

        # Log to audit
        from tools.dynamodb_client import SGAAuditLogger
        audit = SGAAuditLogger()
        audit.log_action(
            action="HIL_TASK_CREATED",
            entity_type="HIL_TASK",
            entity_id=task_id,
            actor=requested_by,
            details={
                "task_type": task_type,
                "related_entity": f"{entity_type}#{entity_id}",
                "priority": priority,
            },
        )

        logger.info("[HIL] Task created: %s (%s)", task_id, task_type)

        return {
            "task_id": task_id,
            "status": HILTaskStatus.PENDING,
            "created_at": now,
            "expires_at": datetime.utcfromtimestamp(ttl_timestamp).isoformat() + "Z",
            "assigned_role": task_item["assigned_role"],
        }

    def _get_default_role(self, task_type: str) -> str:
        """
        Get default role assignment based on task type.

        Args:
            task_type: Type of HIL task

        Returns:
            Role name to assign
        """
        role_map = {
            HILTaskType.APPROVAL_NEW_PN: "INVENTORY_MANAGER",
            HILTaskType.APPROVAL_ENTRY: "INVENTORY_OPERATOR",
            HILTaskType.APPROVAL_ADJUSTMENT: "INVENTORY_MANAGER",
            HILTaskType.APPROVAL_DISCARD: "INVENTORY_MANAGER",
            HILTaskType.APPROVAL_TRANSFER: "INVENTORY_OPERATOR",
            HILTaskType.REVIEW_ENTRY: "INVENTORY_OPERATOR",
            HILTaskType.ESCALATION: "INVENTORY_SUPERVISOR",
        }
        return role_map.get(task_type, "INVENTORY_OPERATOR")

    # =========================================================================
    # Task Queries
    # =========================================================================

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific HIL task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task item or None
        """
        from agents.utils import EntityPrefix

        return self.db.get_item(
            pk=f"{EntityPrefix.TASK}{task_id}",
            sk="METADATA",
            table_name=os.environ.get(
                "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
            ),
        )

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        assigned_to: Optional[str] = None,
        assigned_role: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get pending HIL tasks with optional filters.

        Args:
            task_type: Optional task type filter
            assigned_to: Optional user filter
            assigned_role: Optional role filter
            limit: Maximum tasks to return

        Returns:
            List of pending tasks
        """
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        # Query by status (GSI2)
        tasks = self.db.query_gsi(
            index_name="GSI2",
            pk=f"STATUS#{HILTaskStatus.PENDING}",
            limit=limit,
            table_name=table_name,
        )

        # Filter by task_type if specified
        if task_type:
            tasks = [t for t in tasks if t.get("task_type") == task_type]

        # Filter by assigned_to if specified
        if assigned_to:
            tasks = [t for t in tasks if t.get("assigned_to") == assigned_to]

        # Filter by assigned_role if specified
        if assigned_role:
            tasks = [
                t for t in tasks
                if t.get("assigned_role") == assigned_role
                   or t.get("assigned_to") is None  # Include unassigned
            ]

        return tasks

    def get_tasks_for_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all HIL tasks for a specific entity.

        Args:
            entity_type: Entity type
            entity_id: Entity ID

        Returns:
            List of related tasks
        """
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        return self.db.query_gsi(
            index_name="GSI4",
            pk=f"ENTITY#{entity_type}#{entity_id}",
            table_name=table_name,
        )

    # =========================================================================
    # Task Processing
    # =========================================================================

    async def approve_task(
        self,
        task_id: str,
        approved_by: str,
        notes: Optional[str] = None,
        modified_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending HIL task.

        Args:
            task_id: Task ID to approve
            approved_by: User approving
            notes: Optional approval notes
            modified_payload: Optional modified payload (for MODIFY action)

        Returns:
            Updated task with approval status
        """
        from agents.utils import EntityPrefix, now_iso

        task = self.get_task(task_id)
        if not task:
            # AUDIT-028: Structured error response with user-friendly message
            return {
                "success": False,
                "error": f"Task {task_id} not found",
                "human_explanation": "A tarefa solicitada não foi encontrada no sistema.",
                "suggested_fix": "Verifique o ID da tarefa ou liste as tarefas pendentes primeiro.",
                "recoverable": False,
            }

        if task["status"] != HILTaskStatus.PENDING:
            return {
                "success": False,
                "error": f"Task is not pending. Status: {task['status']}",
                "human_explanation": "Esta tarefa não está mais pendente de aprovação.",
                "suggested_fix": "A tarefa pode já ter sido processada. Verifique o histórico.",
                "recoverable": False,
            }

        now = now_iso()
        new_status = HILTaskStatus.MODIFIED if modified_payload else HILTaskStatus.APPROVED

        # Update task status
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        updates = {
            "status": new_status,
            "processed_at": now,
            "processed_by": approved_by,
            "approval_notes": notes,
            "GSI2_PK": f"STATUS#{new_status}",
            "GSI2_SK": now,
        }

        if modified_payload:
            updates["modified_payload"] = modified_payload

        self.db.update_item(
            pk=f"{EntityPrefix.TASK}{task_id}",
            sk="METADATA",
            updates=updates,
            table_name=table_name,
        )

        # Log to audit
        from tools.dynamodb_client import SGAAuditLogger
        audit = SGAAuditLogger()
        audit.log_action(
            action="HIL_TASK_APPROVED",
            entity_type="HIL_TASK",
            entity_id=task_id,
            actor=approved_by,
            details={
                "task_type": task["task_type"],
                "modified": bool(modified_payload),
            },
        )

        # Execute post-approval action
        execution_result = await self._execute_approved_action(
            task=task,
            modified_payload=modified_payload,
            approved_by=approved_by,
        )

        logger.info("[HIL] Task approved: %s", task_id)

        return {
            "success": True,
            "task_id": task_id,
            "status": new_status,
            "processed_at": now,
            "execution_result": execution_result,
        }

    async def reject_task(
        self,
        task_id: str,
        rejected_by: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Reject a pending HIL task.

        Args:
            task_id: Task ID to reject
            rejected_by: User rejecting
            reason: Rejection reason

        Returns:
            Updated task with rejection status
        """
        from agents.utils import EntityPrefix, now_iso

        task = self.get_task(task_id)
        if not task:
            # AUDIT-028: Structured error response with user-friendly message
            return {
                "success": False,
                "error": f"Task {task_id} not found",
                "human_explanation": "A tarefa solicitada não foi encontrada no sistema.",
                "suggested_fix": "Verifique o ID da tarefa ou liste as tarefas pendentes primeiro.",
                "recoverable": False,
            }

        if task["status"] != HILTaskStatus.PENDING:
            return {
                "success": False,
                "error": f"Task is not pending. Status: {task['status']}",
                "human_explanation": "Esta tarefa não está mais pendente de aprovação.",
                "suggested_fix": "A tarefa pode já ter sido processada. Verifique o histórico.",
                "recoverable": False,
            }

        now = now_iso()
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        # Update task status
        self.db.update_item(
            pk=f"{EntityPrefix.TASK}{task_id}",
            sk="METADATA",
            updates={
                "status": HILTaskStatus.REJECTED,
                "processed_at": now,
                "processed_by": rejected_by,
                "rejection_reason": reason,
                "GSI2_PK": f"STATUS#{HILTaskStatus.REJECTED}",
                "GSI2_SK": now,
            },
            table_name=table_name,
        )

        # Update related entity status if needed
        await self._handle_rejection(task, rejected_by, reason)

        # Log to audit
        from tools.dynamodb_client import SGAAuditLogger
        audit = SGAAuditLogger()
        audit.log_action(
            action="HIL_TASK_REJECTED",
            entity_type="HIL_TASK",
            entity_id=task_id,
            actor=rejected_by,
            details={
                "task_type": task["task_type"],
                "reason": reason[:200],  # Truncate for safety
            },
        )

        logger.info("[HIL] Task rejected: %s", task_id)

        return {
            "success": True,
            "task_id": task_id,
            "status": HILTaskStatus.REJECTED,
            "processed_at": now,
        }

    async def escalate_task(
        self,
        task_id: str,
        escalated_by: str,
        escalation_reason: str,
        escalate_to_role: str = "INVENTORY_SUPERVISOR",
    ) -> Dict[str, Any]:
        """
        Escalate a task to a higher authority.

        Args:
            task_id: Task ID to escalate
            escalated_by: User escalating
            escalation_reason: Why escalating
            escalate_to_role: Role to escalate to

        Returns:
            Updated task with escalation info
        """
        from agents.utils import EntityPrefix, now_iso

        task = self.get_task(task_id)
        if not task:
            # AUDIT-028: Structured error response with user-friendly message
            return {
                "success": False,
                "error": f"Task {task_id} not found",
                "human_explanation": "A tarefa solicitada não foi encontrada no sistema.",
                "suggested_fix": "Verifique o ID da tarefa ou liste as tarefas pendentes primeiro.",
                "recoverable": False,
            }

        now = now_iso()
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        # Update task with escalation
        self.db.update_item(
            pk=f"{EntityPrefix.TASK}{task_id}",
            sk="METADATA",
            updates={
                "priority": HILTaskPriority.URGENT,
                "assigned_role": escalate_to_role,
                "assigned_to": None,  # Clear specific assignment
                "escalated_at": now,
                "escalated_by": escalated_by,
                "escalation_reason": escalation_reason,
                "escalation_history": task.get("escalation_history", []) + [{
                    "from_role": task.get("assigned_role"),
                    "to_role": escalate_to_role,
                    "escalated_at": now,
                    "reason": escalation_reason,
                }],
                "GSI3_PK": f"ASSIGNEE#{escalate_to_role}",
                "GSI3_SK": now,
            },
            table_name=table_name,
        )

        # Log to audit
        from tools.dynamodb_client import SGAAuditLogger
        audit = SGAAuditLogger()
        audit.log_action(
            action="HIL_TASK_ESCALATED",
            entity_type="HIL_TASK",
            entity_id=task_id,
            actor=escalated_by,
            details={
                "from_role": task.get("assigned_role"),
                "to_role": escalate_to_role,
            },
        )

        logger.info("[HIL] Task escalated: %s -> %s", task_id, escalate_to_role)

        return {
            "success": True,
            "task_id": task_id,
            "escalated_to": escalate_to_role,
            "escalated_at": now,
        }

    # =========================================================================
    # Post-Approval Execution
    # =========================================================================

    async def _execute_approved_action(
        self,
        task: Dict[str, Any],
        modified_payload: Optional[Dict[str, Any]],
        approved_by: str,
    ) -> Dict[str, Any]:
        """
        Execute the action after approval.

        This method routes to the appropriate handler based on task type.

        Args:
            task: The approved task
            modified_payload: Optional modified data
            approved_by: User who approved

        Returns:
            Execution result
        """

        task_type = task["task_type"]
        payload = modified_payload or task.get("payload", {})
        entity_type = task["related_entity_type"]
        entity_id = task["related_entity_id"]

        try:
            # Route based on task type
            if task_type == HILTaskType.APPROVAL_TRANSFER:
                return await self._execute_transfer_approval(
                    entity_id=entity_id,
                    payload=payload,
                    approved_by=approved_by,
                )

            elif task_type == HILTaskType.APPROVAL_ADJUSTMENT:
                return await self._execute_adjustment_approval(
                    entity_id=entity_id,
                    payload=payload,
                    approved_by=approved_by,
                )

            elif task_type == HILTaskType.APPROVAL_ENTRY:
                return await self._execute_entry_approval(
                    entity_id=entity_id,
                    payload=payload,
                    approved_by=approved_by,
                )

            elif task_type == HILTaskType.APPROVAL_NEW_PN:
                return await self._execute_new_pn_approval(
                    entity_id=entity_id,
                    payload=payload,
                    approved_by=approved_by,
                )

            elif task_type == HILTaskType.APPROVAL_DISCARD:
                return await self._execute_discard_approval(
                    entity_id=entity_id,
                    payload=payload,
                    approved_by=approved_by,
                )

            else:
                # Generic approval - just update entity status
                return await self._execute_generic_approval(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    approved_by=approved_by,
                )

        except Exception as e:
            logger.error("[HIL] Execution error for task %s: %s", task['task_id'], e)
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_transfer_approval(
        self,
        entity_id: str,
        payload: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        """Execute transfer after approval."""
        from agents.utils import EntityPrefix, now_iso

        # Update movement status
        now = now_iso()
        self.db.update_item(
            pk=f"{EntityPrefix.MOVEMENT}{entity_id}",
            sk="METADATA",
            updates={
                "status": "COMPLETED",
                "approved_at": now,
                "approved_by": approved_by,
            },
        )

        # Execute the actual transfer (balance updates)
        # This would call EstoqueControlAgent._execute_transfer
        # For now, we store the approval and let the agent handle execution

        return {
            "success": True,
            "action": "transfer_approved",
            "movement_id": entity_id,
        }

    async def _execute_adjustment_approval(
        self,
        entity_id: str,
        payload: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        """Execute adjustment after approval."""
        from agents.utils import EntityPrefix, now_iso

        now = now_iso()
        self.db.update_item(
            pk=f"{EntityPrefix.MOVEMENT}{entity_id}",
            sk="METADATA",
            updates={
                "status": "COMPLETED",
                "approved_at": now,
                "approved_by": approved_by,
            },
        )

        return {
            "success": True,
            "action": "adjustment_approved",
            "movement_id": entity_id,
        }

    async def _execute_entry_approval(
        self,
        entity_id: str,
        payload: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        """Execute entry after approval."""
        from agents.utils import EntityPrefix, now_iso

        now = now_iso()
        self.db.update_item(
            pk=f"{EntityPrefix.MOVEMENT}{entity_id}",
            sk="METADATA",
            updates={
                "status": "COMPLETED",
                "approved_at": now,
                "approved_by": approved_by,
            },
        )

        return {
            "success": True,
            "action": "entry_approved",
            "movement_id": entity_id,
        }

    async def _execute_new_pn_approval(
        self,
        entity_id: str,
        payload: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        """Activate new part number after approval."""
        from agents.utils import EntityPrefix, now_iso

        now = now_iso()
        self.db.update_item(
            pk=f"{EntityPrefix.PART_NUMBER}{entity_id}",
            sk="METADATA",
            updates={
                "status": "ACTIVE",
                "activated_at": now,
                "approved_by": approved_by,
            },
        )

        return {
            "success": True,
            "action": "part_number_activated",
            "part_number": entity_id,
        }

    async def _execute_discard_approval(
        self,
        entity_id: str,
        payload: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        """Execute discard after approval."""
        from agents.utils import EntityPrefix, now_iso

        now = now_iso()
        self.db.update_item(
            pk=f"{EntityPrefix.MOVEMENT}{entity_id}",
            sk="METADATA",
            updates={
                "status": "COMPLETED",
                "approved_at": now,
                "approved_by": approved_by,
            },
        )

        return {
            "success": True,
            "action": "discard_approved",
            "movement_id": entity_id,
        }

    async def _execute_generic_approval(
        self,
        entity_type: str,
        entity_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Generic approval handler."""

        # Just log the approval
        from tools.dynamodb_client import SGAAuditLogger
        audit = SGAAuditLogger()
        audit.log_action(
            action="GENERIC_APPROVAL",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=approved_by,
            details={},
        )

        return {
            "success": True,
            "action": "generic_approval",
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    async def _handle_rejection(
        self,
        task: Dict[str, Any],
        rejected_by: str,
        reason: str,
    ) -> None:
        """Handle post-rejection cleanup."""
        from agents.utils import EntityPrefix, now_iso

        entity_type = task["related_entity_type"]
        entity_id = task["related_entity_id"]
        now = now_iso()

        # Update related entity status based on type
        if entity_type == "MOVEMENT":
            self.db.update_item(
                pk=f"{EntityPrefix.MOVEMENT}{entity_id}",
                sk="METADATA",
                updates={
                    "status": "REJECTED",
                    "rejected_at": now,
                    "rejected_by": rejected_by,
                    "rejection_reason": reason,
                },
            )

        elif entity_type == "RESERVATION":
            self.db.update_item(
                pk=f"{EntityPrefix.RESERVATION}{entity_id}",
                sk="METADATA",
                updates={
                    "status": "REJECTED",
                    "rejected_at": now,
                    "rejected_by": rejected_by,
                    "rejection_reason": reason,
                },
            )

        elif entity_type == "PART_NUMBER":
            self.db.update_item(
                pk=f"{EntityPrefix.PART_NUMBER}{entity_id}",
                sk="METADATA",
                updates={
                    "status": "REJECTED",
                    "rejected_at": now,
                    "rejected_by": rejected_by,
                    "rejection_reason": reason,
                },
            )

    # =========================================================================
    # Task Statistics
    # =========================================================================

    def get_task_stats(self) -> Dict[str, Any]:
        """
        Get HIL task statistics.

        Returns:
            Statistics about task states and processing
        """
        table_name = os.environ.get(
            "HIL_TASKS_TABLE", "faiston-one-sga-hil-tasks-prod"
        )

        # Count by status
        pending = len(self.db.query_gsi(
            index_name="GSI2",
            pk=f"STATUS#{HILTaskStatus.PENDING}",
            limit=1000,
            table_name=table_name,
        ))

        approved = len(self.db.query_gsi(
            index_name="GSI2",
            pk=f"STATUS#{HILTaskStatus.APPROVED}",
            limit=1000,
            table_name=table_name,
        ))

        rejected = len(self.db.query_gsi(
            index_name="GSI2",
            pk=f"STATUS#{HILTaskStatus.REJECTED}",
            limit=1000,
            table_name=table_name,
        ))

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total": pending + approved + rejected,
            "approval_rate": (
                approved / (approved + rejected) if (approved + rejected) > 0 else 0
            ),
        }
