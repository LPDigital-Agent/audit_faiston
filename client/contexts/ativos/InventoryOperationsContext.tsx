// =============================================================================
// Inventory Operations Context - SGA Inventory Module
// =============================================================================
// Handles inventory movement operations: reservations, expeditions, transfers,
// returns, and adjustments. Manages operation state and validation.
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
} from 'react';
import {
  createReservation,
  cancelReservation,
  processExpedition,
  createTransfer,
  processReturn,
  validateOperation,
} from '@/services/sgaAgentcore';
import type {
  SGAMovementType,
  SGAReservation,
  SGAMovement,
  SGACreateReservationRequest,
  SGAProcessExpeditionRequest,
  SGACreateTransferRequest,
  SGAProcessReturnRequest,
  ComplianceValidation,
  BackgroundJob,
} from '@/lib/ativos/types';

// =============================================================================
// Constants
// =============================================================================

/** LocalStorage key for persisting background jobs */
const JOBS_STORAGE_KEY = 'sga_background_jobs';

/** Jobs older than this are considered stale and auto-cleaned (1 hour) */
const STALE_JOB_MS = 60 * 60 * 1000;

// =============================================================================
// Types
// =============================================================================

export type OperationStatus = 'idle' | 'validating' | 'processing' | 'success' | 'error';

interface OperationResult<T> {
  success: boolean;
  data?: T;
  error?: string;
  requiresApproval?: boolean;
  hilTaskId?: string;
}

interface InventoryOperationsContextType {
  // Operation state
  operationStatus: OperationStatus;
  operationError: string | null;
  lastValidation: ComplianceValidation | null;

  // Reservation operations
  createNewReservation: (params: SGACreateReservationRequest) => Promise<OperationResult<SGAReservation>>;
  cancelExistingReservation: (reservationId: string, reason: string) => Promise<OperationResult<boolean>>;

  // Expedition operations
  processNewExpedition: (params: SGAProcessExpeditionRequest) => Promise<OperationResult<SGAMovement>>;

  // Transfer operations
  createNewTransfer: (params: SGACreateTransferRequest) => Promise<OperationResult<SGAMovement | undefined>>;

  // Return operations
  processNewReturn: (params: SGAProcessReturnRequest) => Promise<OperationResult<SGAMovement>>;

  // Validation
  validateMovement: (
    operationType: SGAMovementType,
    partNumber: string,
    quantity: number,
    sourceLocationId?: string,
    destinationLocationId?: string,
    projectId?: string
  ) => Promise<ComplianceValidation>;

  // Reset state
  resetOperation: () => void;

  // Background jobs (fire-and-forget async operations)
  activeJobs: BackgroundJob[];
  registerJob: (job: BackgroundJob) => void;
  removeJob: (jobId: string) => void;
  updateJobStatus: (jobId: string, status: BackgroundJob['status'], message?: string) => void;
  hasActiveImportJobs: () => boolean;
  getActiveJobCount: () => number;
}

// =============================================================================
// Context
// =============================================================================

const InventoryOperationsContext = createContext<InventoryOperationsContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface InventoryOperationsProviderProps {
  children: ReactNode;
}

export function InventoryOperationsProvider({ children }: InventoryOperationsProviderProps) {
  const [operationStatus, setOperationStatus] = useState<OperationStatus>('idle');
  const [operationError, setOperationError] = useState<string | null>(null);
  const [lastValidation, setLastValidation] = useState<ComplianceValidation | null>(null);

  // =============================================================================
  // Background Jobs State (Fire-and-Forget Pattern)
  // =============================================================================

  // Initialize from localStorage, filtering out stale jobs
  const [activeJobs, setActiveJobs] = useState<BackgroundJob[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(JOBS_STORAGE_KEY);
      if (!stored) return [];
      const jobs: BackgroundJob[] = JSON.parse(stored);
      // Filter out jobs older than 1 hour (stale)
      const cutoff = Date.now() - STALE_JOB_MS;
      return jobs.filter(j => new Date(j.started_at).getTime() > cutoff);
    } catch {
      return [];
    }
  });

  // Persist jobs to localStorage whenever they change
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(JOBS_STORAGE_KEY, JSON.stringify(activeJobs));
    }
  }, [activeJobs]);

  // Register a new background job
  const registerJob = useCallback((job: BackgroundJob) => {
    setActiveJobs(prev => [...prev, job]);
  }, []);

  // Remove a job by ID
  const removeJob = useCallback((jobId: string) => {
    setActiveJobs(prev => prev.filter(j => j.job_id !== jobId));
  }, []);

  // Update job status (for future polling/websocket integration)
  const updateJobStatus = useCallback((
    jobId: string,
    status: BackgroundJob['status'],
    message?: string
  ) => {
    setActiveJobs(prev => prev.map(j =>
      j.job_id === jobId
        ? {
            ...j,
            status,
            message: message ?? j.message,
            completed_at: (status === 'completed' || status === 'failed')
              ? new Date().toISOString()
              : j.completed_at,
          }
        : j
    ));
  }, []);

  // Check if there are active import jobs
  const hasActiveImportJobs = useCallback(() => {
    return activeJobs.some(j =>
      j.type === 'smart_import' &&
      (j.status === 'queued' || j.status === 'processing')
    );
  }, [activeJobs]);

  // Get count of active jobs
  const getActiveJobCount = useCallback(() => {
    return activeJobs.filter(j =>
      j.status === 'queued' || j.status === 'processing'
    ).length;
  }, [activeJobs]);

  // =============================================================================
  // Operation State Management
  // =============================================================================

  // Reset operation state
  const resetOperation = useCallback(() => {
    setOperationStatus('idle');
    setOperationError(null);
    setLastValidation(null);
  }, []);

  // Validate movement operation
  const validateMovement = useCallback(async (
    operationType: SGAMovementType,
    partNumber: string,
    quantity: number,
    sourceLocationId?: string,
    destinationLocationId?: string,
    projectId?: string
  ): Promise<ComplianceValidation> => {
    setOperationStatus('validating');
    setOperationError(null);

    try {
      const result = await validateOperation({
        operation_type: operationType,
        part_number: partNumber,
        quantity,
        source_location_id: sourceLocationId,
        destination_location_id: destinationLocationId,
        project_id: projectId,
      });

      setLastValidation(result.data.validation);
      setOperationStatus('idle');
      return result.data.validation;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro na validacao';
      setOperationError(message);
      setOperationStatus('error');
      throw error;
    }
  }, []);

  // Create reservation
  const createNewReservation = useCallback(async (
    params: SGACreateReservationRequest
  ): Promise<OperationResult<SGAReservation>> => {
    setOperationStatus('processing');
    setOperationError(null);

    try {
      const result = await createReservation(params);

      setOperationStatus('success');
      return {
        success: true,
        data: result.data.reservation,
        requiresApproval: result.data.requires_approval,
        hilTaskId: result.data.hil_task_id,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao criar reserva';
      setOperationError(message);
      setOperationStatus('error');
      return { success: false, error: message };
    }
  }, []);

  // Cancel reservation
  const cancelExistingReservation = useCallback(async (
    reservationId: string,
    reason: string
  ): Promise<OperationResult<boolean>> => {
    setOperationStatus('processing');
    setOperationError(null);

    try {
      await cancelReservation({ reservation_id: reservationId, reason });

      setOperationStatus('success');
      return { success: true, data: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao cancelar reserva';
      setOperationError(message);
      setOperationStatus('error');
      return { success: false, error: message };
    }
  }, []);

  // Process expedition
  const processNewExpedition = useCallback(async (
    params: SGAProcessExpeditionRequest
  ): Promise<OperationResult<SGAMovement>> => {
    setOperationStatus('processing');
    setOperationError(null);

    try {
      const result = await processExpedition(params);

      setOperationStatus('success');
      return {
        success: true,
        data: result.data.movement,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao processar expedicao';
      setOperationError(message);
      setOperationStatus('error');
      return { success: false, error: message };
    }
  }, []);

  // Create transfer
  const createNewTransfer = useCallback(async (
    params: SGACreateTransferRequest
  ): Promise<OperationResult<SGAMovement | undefined>> => {
    setOperationStatus('processing');
    setOperationError(null);

    try {
      const result = await createTransfer(params);

      setOperationStatus('success');
      return {
        success: true,
        data: result.data.movement,
        requiresApproval: result.data.requires_approval,
        hilTaskId: result.data.hil_task_id,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao criar transferencia';
      setOperationError(message);
      setOperationStatus('error');
      return { success: false, error: message };
    }
  }, []);

  // Process return
  const processNewReturn = useCallback(async (
    params: SGAProcessReturnRequest
  ): Promise<OperationResult<SGAMovement>> => {
    setOperationStatus('processing');
    setOperationError(null);

    try {
      const result = await processReturn(params);

      setOperationStatus('success');
      return {
        success: true,
        data: result.data.movement,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao processar reversa';
      setOperationError(message);
      setOperationStatus('error');
      return { success: false, error: message };
    }
  }, []);

  return (
    <InventoryOperationsContext
      value={{
        operationStatus,
        operationError,
        lastValidation,
        createNewReservation,
        cancelExistingReservation,
        processNewExpedition,
        createNewTransfer,
        processNewReturn,
        validateMovement,
        resetOperation,
        // Background jobs
        activeJobs,
        registerJob,
        removeJob,
        updateJobStatus,
        hasActiveImportJobs,
        getActiveJobCount,
      }}
    >
      {children}
    </InventoryOperationsContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useInventoryOperations() {
  const context = useContext(InventoryOperationsContext);
  if (context === undefined) {
    throw new Error('useInventoryOperations must be used within an InventoryOperationsProvider');
  }
  return context;
}
