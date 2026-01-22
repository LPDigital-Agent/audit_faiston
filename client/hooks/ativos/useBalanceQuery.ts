// =============================================================================
// useBalanceQuery Hook - SGA Inventory Module
// =============================================================================
// Balance queries for part numbers with optional location/project filters.
// =============================================================================

'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getBalance } from '@/services/sgaAgentcore';
import type { SGABalance, SGAGetBalanceRequest } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseBalanceQueryParams extends SGAGetBalanceRequest {
  enabled?: boolean;
}

interface UseBalanceQueryReturn {
  balances: SGABalance[];
  totalAvailable: number;
  totalReserved: number;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => void;
}

// =============================================================================
// Query Keys
// =============================================================================

const BALANCE_QUERY_KEY = 'sga-balance';

// =============================================================================
// Hook
// =============================================================================

export function useBalanceQuery({
  part_number,
  location_id,
  project_id,
  enabled = true,
}: UseBalanceQueryParams): UseBalanceQueryReturn {
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [BALANCE_QUERY_KEY, part_number, location_id, project_id],
    queryFn: async () => {
      const result = await getBalance({
        part_number,
        location_id,
        project_id,
      });
      return result.data;
    },
    enabled: enabled && Boolean(part_number),
    staleTime: 30000, // 30 seconds
  });

  return {
    balances: data?.balances ?? [],
    totalAvailable: data?.total_available ?? 0,
    totalReserved: data?.total_reserved ?? 0,
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  };
}

// Re-export types
export type { SGABalance };
