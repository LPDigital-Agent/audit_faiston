// =============================================================================
// Inventory Count Context - SGA Inventory Module
// =============================================================================
// Manages inventory counting sessions, campaigns, divergences, and adjustments.
// Supports double-count workflows and mobile scanning.
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
  startCampaign,
  submitCount,
  analyzeDivergences,
  proposeAdjustment,
  getActiveCampaigns,
} from '@/services/sgaAgentcore';
import type {
  InventoryCampaign,
  CountResult,
  Divergence,
  AdjustmentProposal,
  SGAStartCampaignRequest,
  SGASubmitCountRequest,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

export interface CountingItem {
  partNumber: string;
  partNumberId: string;
  locationId: string;
  expectedQuantity: number;
  countNumber: number; // 1 or 2 for double-count
  counted?: boolean;
  countedQuantity?: number;
  serialNumbersFound?: string[];
}

interface InventoryCountContextType {
  // Campaign state
  campaigns: InventoryCampaign[];
  campaignsLoading: boolean;
  activeCampaign: InventoryCampaign | null;

  // Counting session state
  countingItems: CountingItem[];
  currentItemIndex: number;
  currentItem: CountingItem | null;
  countResults: CountResult[];

  // Divergences
  divergences: Divergence[];
  divergencesLoading: boolean;
  adjustmentProposals: AdjustmentProposal[];

  // Session state
  isCountingSessionActive: boolean;
  countingProgress: number; // 0-100

  // Actions
  refreshCampaigns: () => Promise<void>;
  startNewCampaign: (params: SGAStartCampaignRequest) => Promise<InventoryCampaign>;
  selectCampaign: (campaign: InventoryCampaign) => void;
  startCountingSession: () => void;
  endCountingSession: () => void;

  // Counting actions
  submitCountResult: (params: Omit<SGASubmitCountRequest, 'campaign_id'>) => Promise<CountResult>;
  skipCurrentItem: () => void;
  goToNextItem: () => void;
  goToPreviousItem: () => void;
  goToItem: (index: number) => void;

  // Divergence actions
  loadDivergences: () => Promise<void>;
  submitAdjustmentProposal: (partNumber: string, locationId: string, reason: string) => Promise<AdjustmentProposal>;

  // Mobile scanning
  lastScannedSerial: string | null;
  addScannedSerial: (serial: string) => void;
  clearScannedSerials: () => void;
  scannedSerials: string[];
}

// =============================================================================
// Context
// =============================================================================

const InventoryCountContext = createContext<InventoryCountContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface InventoryCountProviderProps {
  children: ReactNode;
}

export function InventoryCountProvider({ children }: InventoryCountProviderProps) {
  // Campaigns state
  const [campaigns, setCampaigns] = useState<InventoryCampaign[]>([]);
  const [campaignsLoading, setCampaignsLoading] = useState(true);
  const [activeCampaign, setActiveCampaign] = useState<InventoryCampaign | null>(null);

  // Counting session state
  const [countingItems, setCountingItems] = useState<CountingItem[]>([]);
  const [currentItemIndex, setCurrentItemIndex] = useState(0);
  const [countResults, setCountResults] = useState<CountResult[]>([]);
  const [isCountingSessionActive, setIsCountingSessionActive] = useState(false);

  // Divergences state
  const [divergences, setDivergences] = useState<Divergence[]>([]);
  const [divergencesLoading, setDivergencesLoading] = useState(false);
  const [adjustmentProposals, setAdjustmentProposals] = useState<AdjustmentProposal[]>([]);

  // Scanning state
  const [scannedSerials, setScannedSerials] = useState<string[]>([]);
  const [lastScannedSerial, setLastScannedSerial] = useState<string | null>(null);

  // Derived state
  const currentItem = countingItems[currentItemIndex] || null;
  const countedCount = countingItems.filter(i => i.counted).length;
  const countingProgress = countingItems.length > 0
    ? Math.round((countedCount / countingItems.length) * 100)
    : 0;

  // Load campaigns
  const refreshCampaigns = useCallback(async () => {
    setCampaignsLoading(true);
    try {
      const result = await getActiveCampaigns();
      setCampaigns(result.data.campaigns || []);
    } catch (error) {
      console.error('[InventoryCount] Failed to load campaigns:', error);
    } finally {
      setCampaignsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshCampaigns();
  }, [refreshCampaigns]);

  // Start new campaign
  const startNewCampaign = useCallback(async (params: SGAStartCampaignRequest): Promise<InventoryCampaign> => {
    const result = await startCampaign(params);
    const newCampaign = result.data.campaign;

    setCampaigns(prev => [newCampaign, ...prev]);
    setActiveCampaign(newCampaign);

    return newCampaign;
  }, []);

  // Select campaign
  const selectCampaign = useCallback((campaign: InventoryCampaign) => {
    setActiveCampaign(campaign);
    // TODO: Load counting items from campaign
    setCountingItems([]);
    setCurrentItemIndex(0);
    setCountResults([]);
    setDivergences([]);
  }, []);

  // Start counting session
  const startCountingSession = useCallback(() => {
    if (!activeCampaign) return;
    setIsCountingSessionActive(true);
    setCurrentItemIndex(0);
    setScannedSerials([]);
  }, [activeCampaign]);

  // End counting session
  const endCountingSession = useCallback(() => {
    setIsCountingSessionActive(false);
    setScannedSerials([]);
  }, []);

  // Submit count result
  const submitCountResult = useCallback(async (
    params: Omit<SGASubmitCountRequest, 'campaign_id'>
  ): Promise<CountResult> => {
    if (!activeCampaign) {
      throw new Error('Nenhuma campanha ativa');
    }

    const result = await submitCount({
      campaign_id: activeCampaign.id,
      ...params,
    });

    // Update counting items
    setCountingItems(prev =>
      prev.map((item, idx) =>
        idx === currentItemIndex
          ? {
              ...item,
              counted: true,
              countedQuantity: params.counted_quantity,
              serialNumbersFound: params.serial_numbers_found,
            }
          : item
      )
    );

    // Add to results
    setCountResults(prev => [...prev, result.data.count_result]);

    // If divergence detected, add to list
    if (result.data.divergence) {
      setDivergences(prev => [...prev, result.data.divergence!]);
    }

    // Clear scanned serials
    setScannedSerials([]);

    return result.data.count_result;
  }, [activeCampaign, currentItemIndex]);

  // Navigation
  const skipCurrentItem = useCallback(() => {
    if (currentItemIndex < countingItems.length - 1) {
      setCurrentItemIndex(prev => prev + 1);
      setScannedSerials([]);
    }
  }, [currentItemIndex, countingItems.length]);

  const goToNextItem = useCallback(() => {
    if (currentItemIndex < countingItems.length - 1) {
      setCurrentItemIndex(prev => prev + 1);
      setScannedSerials([]);
    }
  }, [currentItemIndex, countingItems.length]);

  const goToPreviousItem = useCallback(() => {
    if (currentItemIndex > 0) {
      setCurrentItemIndex(prev => prev - 1);
      setScannedSerials([]);
    }
  }, [currentItemIndex]);

  const goToItem = useCallback((index: number) => {
    if (index >= 0 && index < countingItems.length) {
      setCurrentItemIndex(index);
      setScannedSerials([]);
    }
  }, [countingItems.length]);

  // Load divergences
  const loadDivergences = useCallback(async () => {
    if (!activeCampaign) return;

    setDivergencesLoading(true);
    try {
      const result = await analyzeDivergences(activeCampaign.id);
      setDivergences(result.data.divergences || []);
    } catch (error) {
      console.error('[InventoryCount] Failed to load divergences:', error);
    } finally {
      setDivergencesLoading(false);
    }
  }, [activeCampaign]);

  // Submit adjustment proposal
  const submitAdjustmentProposal = useCallback(async (
    partNumber: string,
    locationId: string,
    reason: string
  ): Promise<AdjustmentProposal> => {
    if (!activeCampaign) {
      throw new Error('Nenhuma campanha ativa');
    }

    const result = await proposeAdjustment({
      campaign_id: activeCampaign.id,
      part_number: partNumber,
      location_id: locationId,
      reason,
    });

    setAdjustmentProposals(prev => [...prev, result.data.proposal]);
    return result.data.proposal;
  }, [activeCampaign]);

  // Scanning helpers
  const addScannedSerial = useCallback((serial: string) => {
    setScannedSerials(prev => {
      if (prev.includes(serial)) return prev;
      return [...prev, serial];
    });
    setLastScannedSerial(serial);
  }, []);

  const clearScannedSerials = useCallback(() => {
    setScannedSerials([]);
    setLastScannedSerial(null);
  }, []);

  return (
    <InventoryCountContext.Provider
      value={{
        campaigns,
        campaignsLoading,
        activeCampaign,
        countingItems,
        currentItemIndex,
        currentItem,
        countResults,
        divergences,
        divergencesLoading,
        adjustmentProposals,
        isCountingSessionActive,
        countingProgress,
        refreshCampaigns,
        startNewCampaign,
        selectCampaign,
        startCountingSession,
        endCountingSession,
        submitCountResult,
        skipCurrentItem,
        goToNextItem,
        goToPreviousItem,
        goToItem,
        loadDivergences,
        submitAdjustmentProposal,
        lastScannedSerial,
        addScannedSerial,
        clearScannedSerials,
        scannedSerials,
      }}
    >
      {children}
    </InventoryCountContext.Provider>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useInventoryCount() {
  const context = useContext(InventoryCountContext);
  if (context === undefined) {
    throw new Error('useInventoryCount must be used within an InventoryCountProvider');
  }
  return context;
}
