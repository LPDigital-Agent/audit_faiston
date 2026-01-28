// =============================================================================
// useMovements Hook - SGA Inventory Module
// =============================================================================
// Movement list with filtering and pagination.
// Note: This hook uses the context filters and simulates movement queries
// since the AgentCore doesn't have a dedicated movements endpoint yet.
// =============================================================================


import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { invokeSGAAgentCore } from '@/services/sgaAgentcore';
import { useAssetManagement } from '@/contexts/ativos';
import type { SGAMovement, SGAMovementFilters, SGASortConfig } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseMovementsParams {
  initialPageSize?: number;
  autoFetch?: boolean;
}

interface MovementsResponse {
  movements: SGAMovement[];
  total: number;
  page: number;
  page_size: number;
}

interface UseMovementsReturn {
  // Data
  movements: SGAMovement[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;

  // Pagination
  page: number;
  pageSize: number;
  totalPages: number;
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  goToPage: (page: number) => void;
  nextPage: () => void;
  previousPage: () => void;
  setPageSize: (size: number) => void;

  // Filtering
  filters: SGAMovementFilters;
  setFilter: <K extends keyof SGAMovementFilters>(key: K, value: SGAMovementFilters[K]) => void;
  clearFilters: () => void;

  // Sorting
  sortConfig: SGASortConfig;
  setSortConfig: (config: SGASortConfig) => void;
  toggleSort: (field: string) => void;

  // Actions
  refetch: () => void;
}

// =============================================================================
// Query Keys
// =============================================================================

const MOVEMENTS_QUERY_KEY = 'sga-movements';

// =============================================================================
// Hook
// =============================================================================

export function useMovements({
  initialPageSize = 20,
  autoFetch = true,
}: UseMovementsParams = {}): UseMovementsReturn {
  const { movementFilters, setMovementFilters, resetMovementFilters } = useAssetManagement();

  // Local state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [sortConfig, setSortConfig] = useState<SGASortConfig>({
    field: 'created_at',
    direction: 'desc',
  });

  // Query
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [MOVEMENTS_QUERY_KEY, movementFilters, page, pageSize, sortConfig],
    queryFn: async () => {
      const result = await invokeSGAAgentCore<MovementsResponse>({
        action: 'get_movements',
        query: movementFilters.search || undefined,
        type: movementFilters.type,
        part_number: movementFilters.part_number,
        location_id: movementFilters.location_id,
        project_id: movementFilters.project_id,
        date_from: movementFilters.date_from,
        date_to: movementFilters.date_to,
        page,
        page_size: pageSize,
        sort_field: sortConfig.field,
        sort_direction: sortConfig.direction,
      });
      return result.data;
    },
    enabled: autoFetch,
    staleTime: 30000,
  });

  // Derived values
  const movements = data?.movements ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);
  const hasNextPage = page < totalPages;
  const hasPreviousPage = page > 1;

  // Pagination handlers
  const goToPage = useCallback((newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage);
    }
  }, [totalPages]);

  const nextPage = useCallback(() => {
    if (hasNextPage) {
      setPage(p => p + 1);
    }
  }, [hasNextPage]);

  const previousPage = useCallback(() => {
    if (hasPreviousPage) {
      setPage(p => p - 1);
    }
  }, [hasPreviousPage]);

  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPage(1);
  }, []);

  // Filter handlers
  const setFilter = useCallback(<K extends keyof SGAMovementFilters>(
    key: K,
    value: SGAMovementFilters[K]
  ) => {
    setMovementFilters({ [key]: value });
    setPage(1);
  }, [setMovementFilters]);

  const clearFilters = useCallback(() => {
    resetMovementFilters();
    setPage(1);
  }, [resetMovementFilters]);

  // Sort handlers
  const toggleSort = useCallback((field: string) => {
    setSortConfig(prev => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  }, []);

  return {
    movements,
    total,
    isLoading,
    isError,
    error: error as Error | null,
    page,
    pageSize,
    totalPages,
    hasNextPage,
    hasPreviousPage,
    goToPage,
    nextPage,
    previousPage,
    setPageSize,
    filters: movementFilters,
    setFilter,
    clearFilters,
    sortConfig,
    setSortConfig,
    toggleSort,
    refetch,
  };
}

// Re-export types
export type { SGAMovement, SGAMovementFilters };
