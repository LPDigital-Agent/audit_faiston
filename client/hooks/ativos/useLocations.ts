// =============================================================================
// useLocations Hook - SGA Inventory Module
// =============================================================================
// Location management with CRUD operations.
// =============================================================================

'use client';

import { useMemo, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAssetManagement } from '@/contexts/ativos';
import { createLocation } from '@/services/sgaAgentcore';
import type { SGALocation } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseLocationsReturn {
  // Data
  locations: SGALocation[];
  isLoading: boolean;
  error: string | null;

  // Filtered locations
  activeLocations: SGALocation[];
  warehouseLocations: SGALocation[];
  customerLocations: SGALocation[];
  restrictedLocations: SGALocation[];

  // Lookup
  getLocationById: (id: string) => SGALocation | undefined;
  getLocationByCode: (code: string) => SGALocation | undefined;

  // Mutations
  createNewLocation: {
    mutate: (params: Omit<SGALocation, 'id' | 'created_at' | 'updated_at'>) => void;
    mutateAsync: (params: Omit<SGALocation, 'id' | 'created_at' | 'updated_at'>) => Promise<SGALocation>;
    isPending: boolean;
    isError: boolean;
    error: Error | null;
  };

  // Actions
  refresh: () => Promise<void>;
}

// =============================================================================
// Hook
// =============================================================================

export function useLocations(): UseLocationsReturn {
  const queryClient = useQueryClient();
  const {
    locations,
    masterDataLoading,
    masterDataError,
    refreshMasterData,
    getLocationById,
  } = useAssetManagement();

  // Filtered locations
  const activeLocations = useMemo(
    () => locations.filter(loc => loc.is_active),
    [locations]
  );

  const warehouseLocations = useMemo(
    () => locations.filter(loc => loc.type === 'WAREHOUSE' && loc.is_active),
    [locations]
  );

  const customerLocations = useMemo(
    () => locations.filter(loc => loc.type === 'CUSTOMER' && loc.is_active),
    [locations]
  );

  const restrictedLocations = useMemo(
    () => locations.filter(loc => loc.is_restricted && loc.is_active),
    [locations]
  );

  // Lookup by code
  const getLocationByCode = useCallback(
    (code: string) => locations.find(loc => loc.code === code),
    [locations]
  );

  // Create location mutation
  const createLocationMutation = useMutation({
    mutationFn: async (params: Omit<SGALocation, 'id' | 'created_at' | 'updated_at'>) => {
      const result = await createLocation(params);
      return result.data.location;
    },
    onSuccess: () => {
      refreshMasterData();
    },
  });

  return {
    locations,
    isLoading: masterDataLoading,
    error: masterDataError,
    activeLocations,
    warehouseLocations,
    customerLocations,
    restrictedLocations,
    getLocationById,
    getLocationByCode,
    createNewLocation: {
      mutate: createLocationMutation.mutate,
      mutateAsync: createLocationMutation.mutateAsync,
      isPending: createLocationMutation.isPending,
      isError: createLocationMutation.isError,
      error: createLocationMutation.error,
    },
    refresh: refreshMasterData,
  };
}

// Re-export types
export type { SGALocation };
