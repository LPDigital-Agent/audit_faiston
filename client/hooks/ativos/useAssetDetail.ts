// =============================================================================
// useAssetDetail Hook - SGA Inventory Module
// =============================================================================
// Single asset detail with timeline and related data.
// =============================================================================

'use client';

import { useQuery } from '@tanstack/react-query';
import { whereIsSerial } from '@/services/sgaAgentcore';
import type { SGAAsset, SGAMovement } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseAssetDetailParams {
  serialNumber: string;
  enabled?: boolean;
}

interface UseAssetDetailReturn {
  asset: SGAAsset | null;
  timeline: SGAMovement[];
  found: boolean;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => void;
}

// =============================================================================
// Query Keys
// =============================================================================

const ASSET_DETAIL_QUERY_KEY = 'sga-asset-detail';

// =============================================================================
// Hook
// =============================================================================

export function useAssetDetail({
  serialNumber,
  enabled = true,
}: UseAssetDetailParams): UseAssetDetailReturn {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: [ASSET_DETAIL_QUERY_KEY, serialNumber],
    queryFn: async () => {
      const result = await whereIsSerial({ serial_number: serialNumber });
      return result.data;
    },
    enabled: enabled && Boolean(serialNumber),
    staleTime: 60000, // 1 minute
  });

  return {
    asset: data?.asset ?? null,
    timeline: data?.timeline ?? [],
    found: data?.found ?? false,
    isLoading,
    isError,
    error: error as Error | null,
    refetch,
  };
}

// Re-export types
export type { SGAAsset, SGAMovement };
