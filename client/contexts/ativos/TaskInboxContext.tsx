// =============================================================================
// Task Inbox Context - SGA Inventory Module
// =============================================================================
// Real-time HIL (Human-in-the-Loop) task management for approvals and reviews.
// Handles task loading, polling, and status updates.
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
  useRef,
} from 'react';
import {
  getPendingTasks,
  approveTask,
  rejectTask,
} from '@/services/sgaAgentcore';
import type {
  HILTask,
  HILTaskType,
  HILTaskStatus,
  SGAApproveTaskResponse,
  SGARejectTaskResponse,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface TaskInboxContextType {
  // Tasks state
  tasks: HILTask[];
  tasksLoading: boolean;
  tasksError: string | null;

  // Task counts by type
  taskCounts: Record<HILTaskType, number>;
  totalPending: number;

  // Actions
  refreshTasks: () => Promise<void>;
  handleApprove: (taskId: string, notes?: string) => Promise<SGAApproveTaskResponse>;
  handleReject: (taskId: string, reason: string) => Promise<SGARejectTaskResponse>;

  // Filters
  typeFilter: HILTaskType | null;
  setTypeFilter: (type: HILTaskType | null) => void;
  statusFilter: HILTaskStatus | null;
  setStatusFilter: (status: HILTaskStatus | null) => void;

  // Polling
  isPolling: boolean;
  setPollingEnabled: (enabled: boolean) => void;
  pollingInterval: number;
  setPollingInterval: (ms: number) => void;

  // Selected task
  selectedTask: HILTask | null;
  setSelectedTask: (task: HILTask | null) => void;
}

// =============================================================================
// Context
// =============================================================================

const TaskInboxContext = createContext<TaskInboxContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface TaskInboxProviderProps {
  children: ReactNode;
  pollingEnabled?: boolean;
  initialPollingInterval?: number;
}

const DEFAULT_POLLING_INTERVAL = 30000; // 30 seconds

export function TaskInboxProvider({
  children,
  pollingEnabled = false, // Disabled: get_pending_tasks action not implemented on backend
  initialPollingInterval = DEFAULT_POLLING_INTERVAL,
}: TaskInboxProviderProps) {
  // Tasks state
  const [tasks, setTasks] = useState<HILTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [tasksError, setTasksError] = useState<string | null>(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState<HILTaskType | null>(null);
  const [statusFilter, setStatusFilter] = useState<HILTaskStatus | null>(null);

  // Polling state
  const [isPolling, setIsPolling] = useState(pollingEnabled);
  const [pollingInterval, setPollingInterval] = useState(initialPollingInterval);

  // Selected task
  const [selectedTask, setSelectedTask] = useState<HILTask | null>(null);

  // Polling interval ref
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // Calculate task counts by type
  const taskCounts = tasks.reduce((acc, task) => {
    if (task.status === 'PENDING') {
      acc[task.type] = (acc[task.type] || 0) + 1;
    }
    return acc;
  }, {} as Record<HILTaskType, number>);

  const totalPending = tasks.filter(t => t.status === 'PENDING').length;

  // Fetch tasks
  const refreshTasks = useCallback(async () => {
    setTasksLoading(true);
    setTasksError(null);

    try {
      const result = await getPendingTasks({
        type: typeFilter || undefined,
        status: statusFilter || undefined,
      });

      setTasks(result.data.tasks || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao carregar tarefas';
      setTasksError(message);
      console.error('[TaskInbox] Failed to load tasks:', error);
    } finally {
      setTasksLoading(false);
    }
  }, [typeFilter, statusFilter]);

  // Initial load
  useEffect(() => {
    refreshTasks();
  }, [refreshTasks]);

  // Polling setup
  useEffect(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    if (isPolling && pollingInterval > 0) {
      pollingRef.current = setInterval(() => {
        refreshTasks();
      }, pollingInterval);
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [isPolling, pollingInterval, refreshTasks]);

  // Approve task
  const handleApprove = useCallback(async (taskId: string, notes?: string): Promise<SGAApproveTaskResponse> => {
    const result = await approveTask({ task_id: taskId, notes });

    // Update local state
    setTasks(prev =>
      prev.map(t =>
        t.id === taskId
          ? { ...t, status: 'APPROVED' as const, resolved_at: new Date().toISOString() }
          : t
      )
    );

    // Clear selection if it was the selected task
    if (selectedTask?.id === taskId) {
      setSelectedTask(null);
    }

    return result.data;
  }, [selectedTask]);

  // Reject task
  const handleReject = useCallback(async (taskId: string, reason: string): Promise<SGARejectTaskResponse> => {
    const result = await rejectTask({ task_id: taskId, reason });

    // Update local state
    setTasks(prev =>
      prev.map(t =>
        t.id === taskId
          ? {
              ...t,
              status: 'REJECTED' as const,
              resolved_at: new Date().toISOString(),
              resolution_notes: reason,
            }
          : t
      )
    );

    // Clear selection if it was the selected task
    if (selectedTask?.id === taskId) {
      setSelectedTask(null);
    }

    return result.data;
  }, [selectedTask]);

  // Polling control
  const setPollingEnabled = useCallback((enabled: boolean) => {
    setIsPolling(enabled);
  }, []);

  return (
    <TaskInboxContext
      value={{
        tasks,
        tasksLoading,
        tasksError,
        taskCounts,
        totalPending,
        refreshTasks,
        handleApprove,
        handleReject,
        typeFilter,
        setTypeFilter,
        statusFilter,
        setStatusFilter,
        isPolling,
        setPollingEnabled,
        pollingInterval,
        setPollingInterval,
        selectedTask,
        setSelectedTask,
      }}
    >
      {children}
    </TaskInboxContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useTaskInbox() {
  const context = useContext(TaskInboxContext);
  if (context === undefined) {
    throw new Error('useTaskInbox must be used within a TaskInboxProvider');
  }
  return context;
}
