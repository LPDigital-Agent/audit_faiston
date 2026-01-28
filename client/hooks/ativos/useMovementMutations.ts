// =============================================================================
// useMovementMutations Hook - SGA Inventory Module
// =============================================================================
// Mutations for movement operations: reservations, expeditions, transfers, returns.
// Wraps the InventoryOperationsContext with TanStack Query mutations.
// =============================================================================


import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useInventoryOperations } from '@/contexts/ativos';
import { safeExtractErrorMessage } from '@/utils/agentcoreResponse';  // BUG-022: Handle double-encoded errors
import type {
  SGACreateReservationRequest,
  SGAProcessExpeditionRequest,
  SGACreateTransferRequest,
  SGAProcessReturnRequest,
  SGAReservation,
  SGAMovement,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseMovementMutationsReturn {
  // Reservation mutations
  createReservation: {
    mutate: (params: SGACreateReservationRequest) => void;
    mutateAsync: (params: SGACreateReservationRequest) => Promise<SGAReservation | undefined>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    data: SGAReservation | undefined;
  };
  cancelReservation: {
    mutate: (params: { reservationId: string; reason: string }) => void;
    mutateAsync: (params: { reservationId: string; reason: string }) => Promise<boolean>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
  };

  // Expedition mutations
  processExpedition: {
    mutate: (params: SGAProcessExpeditionRequest) => void;
    mutateAsync: (params: SGAProcessExpeditionRequest) => Promise<SGAMovement | undefined>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    data: SGAMovement | undefined;
  };

  // Transfer mutations
  createTransfer: {
    mutate: (params: SGACreateTransferRequest) => void;
    mutateAsync: (params: SGACreateTransferRequest) => Promise<SGAMovement | undefined>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    data: SGAMovement | undefined;
    requiresApproval?: boolean;
  };

  // Return mutations
  processReturn: {
    mutate: (params: SGAProcessReturnRequest) => void;
    mutateAsync: (params: SGAProcessReturnRequest) => Promise<SGAMovement | undefined>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    data: SGAMovement | undefined;
  };

  // Global state
  operationStatus: string;
  operationError: string | null;
  resetOperation: () => void;
}

// =============================================================================
// Hook
// =============================================================================

export function useMovementMutations(): UseMovementMutationsReturn {
  const queryClient = useQueryClient();
  const {
    createNewReservation,
    cancelExistingReservation,
    processNewExpedition,
    createNewTransfer,
    processNewReturn,
    operationStatus,
    operationError,
    resetOperation,
  } = useInventoryOperations();

  // Invalidate related queries after mutations
  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
    queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
    queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
  };

  // Create reservation mutation
  const createReservationMutation = useMutation({
    mutationFn: async (params: SGACreateReservationRequest) => {
      const result = await createNewReservation(params);
      if (!result.success) {
        throw new Error(safeExtractErrorMessage(result.error));  // BUG-022 FIX
      }
      return result.data;
    },
    onSuccess: () => {
      invalidateQueries();
    },
  });

  // Cancel reservation mutation
  const cancelReservationMutation = useMutation({
    mutationFn: async ({ reservationId, reason }: { reservationId: string; reason: string }) => {
      const result = await cancelExistingReservation(reservationId, reason);
      if (!result.success) {
        throw new Error(safeExtractErrorMessage(result.error));  // BUG-022 FIX
      }
      return result.data!;
    },
    onSuccess: () => {
      invalidateQueries();
    },
  });

  // Process expedition mutation
  const processExpeditionMutation = useMutation({
    mutationFn: async (params: SGAProcessExpeditionRequest) => {
      const result = await processNewExpedition(params);
      if (!result.success) {
        throw new Error(safeExtractErrorMessage(result.error));  // BUG-022 FIX
      }
      return result.data;
    },
    onSuccess: () => {
      invalidateQueries();
    },
  });

  // Create transfer mutation
  const createTransferMutation = useMutation({
    mutationFn: async (params: SGACreateTransferRequest) => {
      const result = await createNewTransfer(params);
      if (!result.success) {
        throw new Error(safeExtractErrorMessage(result.error));  // BUG-022 FIX
      }
      return result.data;
    },
    onSuccess: () => {
      invalidateQueries();
    },
  });

  // Process return mutation
  const processReturnMutation = useMutation({
    mutationFn: async (params: SGAProcessReturnRequest) => {
      const result = await processNewReturn(params);
      if (!result.success) {
        throw new Error(safeExtractErrorMessage(result.error));  // BUG-022 FIX
      }
      return result.data;
    },
    onSuccess: () => {
      invalidateQueries();
    },
  });

  return {
    createReservation: {
      mutate: createReservationMutation.mutate,
      mutateAsync: createReservationMutation.mutateAsync,
      isPending: createReservationMutation.isPending,
      isError: createReservationMutation.isError,
      error: createReservationMutation.error,
      data: createReservationMutation.data,
    },
    cancelReservation: {
      mutate: cancelReservationMutation.mutate,
      mutateAsync: cancelReservationMutation.mutateAsync,
      isPending: cancelReservationMutation.isPending,
      isError: cancelReservationMutation.isError,
      error: cancelReservationMutation.error,
    },
    processExpedition: {
      mutate: processExpeditionMutation.mutate,
      mutateAsync: processExpeditionMutation.mutateAsync,
      isPending: processExpeditionMutation.isPending,
      isError: processExpeditionMutation.isError,
      error: processExpeditionMutation.error,
      data: processExpeditionMutation.data,
    },
    createTransfer: {
      mutate: createTransferMutation.mutate,
      mutateAsync: createTransferMutation.mutateAsync,
      isPending: createTransferMutation.isPending,
      isError: createTransferMutation.isError,
      error: createTransferMutation.error,
      data: createTransferMutation.data,
    },
    processReturn: {
      mutate: processReturnMutation.mutate,
      mutateAsync: processReturnMutation.mutateAsync,
      isPending: processReturnMutation.isPending,
      isError: processReturnMutation.isError,
      error: processReturnMutation.error,
      data: processReturnMutation.data,
    },
    operationStatus,
    operationError,
    resetOperation,
  };
}

// Re-export types
export type {
  SGACreateReservationRequest,
  SGAProcessExpeditionRequest,
  SGACreateTransferRequest,
  SGAProcessReturnRequest,
  SGAReservation,
  SGAMovement,
};
