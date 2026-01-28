// =============================================================================
// usePartNumbers Hook - SGA Inventory Module
// =============================================================================
// Part number (SKU/catalog) management with CRUD operations.
// =============================================================================


import { useMemo, useCallback, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useAssetManagement } from '@/contexts/ativos';
import { createPartNumber } from '@/services/sgaAgentcore';
import type { SGAPartNumber } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UsePartNumbersReturn {
  // Data
  partNumbers: SGAPartNumber[];
  isLoading: boolean;
  error: string | null;

  // Search/filter
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  filteredPartNumbers: SGAPartNumber[];

  // Filtered part numbers
  activePartNumbers: SGAPartNumber[];
  serializedPartNumbers: SGAPartNumber[];
  categorizedPartNumbers: Record<string, SGAPartNumber[]>;

  // Lookup
  getPartNumberById: (id: string) => SGAPartNumber | undefined;
  getPartNumberByCode: (code: string) => SGAPartNumber | undefined;

  // Mutations
  createNewPartNumber: {
    mutate: (params: Omit<SGAPartNumber, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => void;
    mutateAsync: (params: Omit<SGAPartNumber, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => Promise<SGAPartNumber | undefined>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
    requiresApproval?: boolean;
    hilTaskId?: string;
  };

  // Actions
  refresh: () => Promise<void>;
}

// =============================================================================
// Hook
// =============================================================================

export function usePartNumbers(): UsePartNumbersReturn {
  const {
    partNumbers,
    masterDataLoading,
    masterDataError,
    refreshMasterData,
    getPartNumberById,
  } = useAssetManagement();

  // Local search state
  const [searchTerm, setSearchTerm] = useState('');
  const [hilTaskId, setHilTaskId] = useState<string | undefined>();
  const [requiresApproval, setRequiresApproval] = useState(false);

  // Filtered by search
  const filteredPartNumbers = useMemo(() => {
    if (!searchTerm) return partNumbers;
    const term = searchTerm.toLowerCase();
    return partNumbers.filter(
      pn =>
        pn.part_number.toLowerCase().includes(term) ||
        pn.description.toLowerCase().includes(term) ||
        pn.category?.toLowerCase().includes(term)
    );
  }, [partNumbers, searchTerm]);

  // Filtered lists
  const activePartNumbers = useMemo(
    () => partNumbers.filter(pn => pn.is_active),
    [partNumbers]
  );

  const serializedPartNumbers = useMemo(
    () => partNumbers.filter(pn => pn.is_serialized && pn.is_active),
    [partNumbers]
  );

  // Grouped by category
  const categorizedPartNumbers = useMemo(() => {
    return partNumbers.reduce((acc, pn) => {
      const category = pn.category || 'Outros';
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(pn);
      return acc;
    }, {} as Record<string, SGAPartNumber[]>);
  }, [partNumbers]);

  // Lookup by code
  const getPartNumberByCode = useCallback(
    (code: string) => partNumbers.find(pn => pn.part_number === code),
    [partNumbers]
  );

  // Create part number mutation
  const createPartNumberMutation = useMutation({
    mutationFn: async (params: Omit<SGAPartNumber, 'id' | 'created_at' | 'updated_at' | 'created_by'>) => {
      const result = await createPartNumber(params);

      // Check if it requires approval
      if (result.data.hil_task_id) {
        setHilTaskId(result.data.hil_task_id);
        setRequiresApproval(true);
        return undefined; // Not created yet, pending approval
      }

      setRequiresApproval(false);
      setHilTaskId(undefined);
      return result.data.part_number;
    },
    onSuccess: (data) => {
      if (data) {
        refreshMasterData();
      }
    },
  });

  return {
    partNumbers,
    isLoading: masterDataLoading,
    error: masterDataError,
    searchTerm,
    setSearchTerm,
    filteredPartNumbers,
    activePartNumbers,
    serializedPartNumbers,
    categorizedPartNumbers,
    getPartNumberById,
    getPartNumberByCode,
    createNewPartNumber: {
      mutate: createPartNumberMutation.mutate,
      mutateAsync: createPartNumberMutation.mutateAsync,
      isPending: createPartNumberMutation.isPending,
      isError: createPartNumberMutation.isError,
      error: createPartNumberMutation.error,
      requiresApproval,
      hilTaskId,
    },
    refresh: refreshMasterData,
  };
}

// Re-export types
export type { SGAPartNumber };
