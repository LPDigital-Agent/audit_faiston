// =============================================================================
// useAssets Hook - SGA Inventory Module
// =============================================================================
// Asset list management with pagination, filtering, and sorting.
// Uses TanStack Query for data fetching and caching.
// =============================================================================

'use client';

import { useState, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { searchAssets } from '@/services/sgaAgentcore';
import { useAssetManagement } from '@/contexts/ativos';
import type { SGAAsset, SGAAssetFilters, SGASortConfig } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseAssetsParams {
  initialPageSize?: number;
  autoFetch?: boolean;
}

interface UseAssetsReturn {
  // Data
  assets: SGAAsset[];
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

  // Filtering (uses context filters)
  filters: SGAAssetFilters;
  setFilter: <K extends keyof SGAAssetFilters>(key: K, value: SGAAssetFilters[K]) => void;
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

const ASSETS_QUERY_KEY = 'sga-assets';

// =============================================================================
// Hook
// =============================================================================

export function useAssets({
  initialPageSize = 20,
  autoFetch = true,
}: UseAssetsParams = {}): UseAssetsReturn {
  const queryClient = useQueryClient();
  const { assetFilters, setAssetFilters, resetAssetFilters } = useAssetManagement();

  // Local state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);
  const [sortConfig, setSortConfig] = useState<SGASortConfig>({
    field: 'updated_at',
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
    queryKey: [ASSETS_QUERY_KEY, assetFilters, page, pageSize, sortConfig],
    queryFn: async () => {
      const result = await searchAssets({
        query: assetFilters.search || undefined,
        part_number: assetFilters.part_number,
        location_id: assetFilters.location_id,
        project_id: assetFilters.project_id,
        status: assetFilters.status,
        page,
        page_size: pageSize,
      });
      return result.data;
    },
    enabled: autoFetch,
    staleTime: 30000, // 30 seconds
  });

  // Derived values
  const assets = data?.assets ?? [];
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
    setPage(1); // Reset to first page
  }, []);

  // Filter handlers
  const setFilter = useCallback(<K extends keyof SGAAssetFilters>(
    key: K,
    value: SGAAssetFilters[K]
  ) => {
    setAssetFilters({ [key]: value });
    setPage(1); // Reset to first page
  }, [setAssetFilters]);

  const clearFilters = useCallback(() => {
    resetAssetFilters();
    setPage(1);
  }, [resetAssetFilters]);

  // Sort handlers
  const toggleSort = useCallback((field: string) => {
    setSortConfig(prev => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  }, []);

  // Refetch handler
  const handleRefetch = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [ASSETS_QUERY_KEY] });
    refetch();
  }, [queryClient, refetch]);

  return {
    assets,
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
    filters: assetFilters,
    setFilter,
    clearFilters,
    sortConfig,
    setSortConfig,
    toggleSort,
    refetch: handleRefetch,
  };
}

// Re-export types
export type { SGAAsset, SGAAssetFilters, SGASortConfig };
