// =============================================================================
// Asset Management Context - SGA Inventory Module
// =============================================================================
// Global state management for the SGA (Sistema de Gestao de Ativos) module.
// Handles master data, filters, selected items, and user preferences.
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
  useMemo,
} from 'react';
import { SGA_STORAGE_KEYS } from '@/lib/ativos/constants';
import {
  getPartNumbers,
  getLocations,
  getProjects,
  getDashboardSummary,
} from '@/services/sgaAgentcore';
import type {
  SGAPartNumber,
  SGALocation,
  SGAProject,
  SGAAssetFilters,
  SGAMovementFilters,
  SGADashboardSummary,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface AssetManagementContextType {
  // Master data
  partNumbers: SGAPartNumber[];
  locations: SGALocation[];
  projects: SGAProject[];
  masterDataLoading: boolean;
  masterDataError: string | null;
  refreshMasterData: () => Promise<void>;

  // Dashboard
  dashboardSummary: SGADashboardSummary | null;
  dashboardLoading: boolean;
  refreshDashboard: () => Promise<void>;

  // Asset filters
  assetFilters: SGAAssetFilters;
  setAssetFilters: (filters: Partial<SGAAssetFilters>) => void;
  resetAssetFilters: () => void;

  // Movement filters
  movementFilters: SGAMovementFilters;
  setMovementFilters: (filters: Partial<SGAMovementFilters>) => void;
  resetMovementFilters: () => void;

  // Selected items
  selectedAssetIds: string[];
  setSelectedAssetIds: (ids: string[]) => void;
  toggleAssetSelection: (id: string) => void;
  clearAssetSelection: () => void;

  // User preferences
  lastLocationId: string | null;
  setLastLocationId: (id: string) => void;
  lastProjectId: string | null;
  setLastProjectId: (id: string) => void;

  // Helpers
  getPartNumberById: (id: string) => SGAPartNumber | undefined;
  getLocationById: (id: string) => SGALocation | undefined;
  getProjectById: (id: string) => SGAProject | undefined;
}

const DEFAULT_ASSET_FILTERS: SGAAssetFilters = {
  search: '',
  part_number: undefined,
  location_id: undefined,
  project_id: undefined,
  status: undefined,
  date_from: undefined,
  date_to: undefined,
};

const DEFAULT_MOVEMENT_FILTERS: SGAMovementFilters = {
  search: '',
  type: undefined,
  part_number: undefined,
  location_id: undefined,
  project_id: undefined,
  date_from: undefined,
  date_to: undefined,
};

// =============================================================================
// Context
// =============================================================================

const AssetManagementContext = createContext<AssetManagementContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface AssetManagementProviderProps {
  children: ReactNode;
}

export function AssetManagementProvider({ children }: AssetManagementProviderProps) {
  // Master data state
  const [partNumbers, setPartNumbers] = useState<SGAPartNumber[]>([]);
  const [locations, setLocations] = useState<SGALocation[]>([]);
  const [projects, setProjects] = useState<SGAProject[]>([]);
  const [masterDataLoading, setMasterDataLoading] = useState(true);
  const [masterDataError, setMasterDataError] = useState<string | null>(null);

  // Dashboard state
  const [dashboardSummary, setDashboardSummary] = useState<SGADashboardSummary | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  // Filters state (persisted to localStorage)
  const [assetFilters, setAssetFiltersState] = useState<SGAAssetFilters>(() => {
    if (typeof window === 'undefined') return DEFAULT_ASSET_FILTERS;
    try {
      const stored = localStorage.getItem(SGA_STORAGE_KEYS.ASSET_FILTERS);
      return stored ? { ...DEFAULT_ASSET_FILTERS, ...JSON.parse(stored) } : DEFAULT_ASSET_FILTERS;
    } catch {
      return DEFAULT_ASSET_FILTERS;
    }
  });

  const [movementFilters, setMovementFiltersState] = useState<SGAMovementFilters>(() => {
    if (typeof window === 'undefined') return DEFAULT_MOVEMENT_FILTERS;
    try {
      const stored = localStorage.getItem(SGA_STORAGE_KEYS.MOVEMENT_FILTERS);
      return stored ? { ...DEFAULT_MOVEMENT_FILTERS, ...JSON.parse(stored) } : DEFAULT_MOVEMENT_FILTERS;
    } catch {
      return DEFAULT_MOVEMENT_FILTERS;
    }
  });

  // Selection state
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([]);

  // User preferences (persisted)
  const [lastLocationId, setLastLocationIdState] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SGA_STORAGE_KEYS.LAST_LOCATION);
  });

  const [lastProjectId, setLastProjectIdState] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(SGA_STORAGE_KEYS.LAST_PROJECT);
  });

  // Load master data on mount
  const refreshMasterData = useCallback(async () => {
    setMasterDataLoading(true);
    setMasterDataError(null);

    try {
      const [pnResult, locResult, projResult] = await Promise.all([
        getPartNumbers(),
        getLocations(),
        getProjects(),
      ]);

      setPartNumbers(pnResult.data.part_numbers || []);
      setLocations(locResult.data.locations || []);
      setProjects(projResult.data.projects || []);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao carregar dados mestres';
      setMasterDataError(message);
      console.error('[AssetManagement] Failed to load master data:', error);
    } finally {
      setMasterDataLoading(false);
    }
  }, []);

  // Load dashboard summary
  const refreshDashboard = useCallback(async () => {
    setDashboardLoading(true);

    try {
      const result = await getDashboardSummary();
      setDashboardSummary(result.data);
    } catch (error) {
      console.error('[AssetManagement] Failed to load dashboard:', error);
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  // Initial data load
  useEffect(() => {
    refreshMasterData();
    refreshDashboard();
  }, [refreshMasterData, refreshDashboard]);

  // Persist filters to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(SGA_STORAGE_KEYS.ASSET_FILTERS, JSON.stringify(assetFilters));
  }, [assetFilters]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(SGA_STORAGE_KEYS.MOVEMENT_FILTERS, JSON.stringify(movementFilters));
  }, [movementFilters]);

  // Filter setters
  const setAssetFilters = useCallback((filters: Partial<SGAAssetFilters>) => {
    setAssetFiltersState(prev => ({ ...prev, ...filters }));
  }, []);

  const resetAssetFilters = useCallback(() => {
    setAssetFiltersState(DEFAULT_ASSET_FILTERS);
  }, []);

  const setMovementFilters = useCallback((filters: Partial<SGAMovementFilters>) => {
    setMovementFiltersState(prev => ({ ...prev, ...filters }));
  }, []);

  const resetMovementFilters = useCallback(() => {
    setMovementFiltersState(DEFAULT_MOVEMENT_FILTERS);
  }, []);

  // Selection helpers
  const toggleAssetSelection = useCallback((id: string) => {
    setSelectedAssetIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  }, []);

  const clearAssetSelection = useCallback(() => {
    setSelectedAssetIds([]);
  }, []);

  // User preferences setters
  const setLastLocationId = useCallback((id: string) => {
    setLastLocationIdState(id);
    if (typeof window !== 'undefined') {
      localStorage.setItem(SGA_STORAGE_KEYS.LAST_LOCATION, id);
    }
  }, []);

  const setLastProjectId = useCallback((id: string) => {
    setLastProjectIdState(id);
    if (typeof window !== 'undefined') {
      localStorage.setItem(SGA_STORAGE_KEYS.LAST_PROJECT, id);
    }
  }, []);

  // Lookup helpers (memoized maps)
  const partNumberMap = useMemo(
    () => new Map(partNumbers.map(pn => [pn.id, pn])),
    [partNumbers]
  );

  const locationMap = useMemo(
    () => new Map(locations.map(loc => [loc.id, loc])),
    [locations]
  );

  const projectMap = useMemo(
    () => new Map(projects.map(proj => [proj.id, proj])),
    [projects]
  );

  const getPartNumberById = useCallback(
    (id: string) => partNumberMap.get(id),
    [partNumberMap]
  );

  const getLocationById = useCallback(
    (id: string) => locationMap.get(id),
    [locationMap]
  );

  const getProjectById = useCallback(
    (id: string) => projectMap.get(id),
    [projectMap]
  );

  return (
    <AssetManagementContext
      value={{
        partNumbers,
        locations,
        projects,
        masterDataLoading,
        masterDataError,
        refreshMasterData,
        dashboardSummary,
        dashboardLoading,
        refreshDashboard,
        assetFilters,
        setAssetFilters,
        resetAssetFilters,
        movementFilters,
        setMovementFilters,
        resetMovementFilters,
        selectedAssetIds,
        setSelectedAssetIds,
        toggleAssetSelection,
        clearAssetSelection,
        lastLocationId,
        setLastLocationId,
        lastProjectId,
        setLastProjectId,
        getPartNumberById,
        getLocationById,
        getProjectById,
      }}
    >
      {children}
    </AssetManagementContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useAssetManagement() {
  const context = useContext(AssetManagementContext);
  if (context === undefined) {
    throw new Error('useAssetManagement must be used within an AssetManagementProvider');
  }
  return context;
}
