// =============================================================================
// Offline Sync Context - SGA Inventory Module
// =============================================================================
// PWA offline support with queue-based sync for mobile operations.
// Handles offline detection, queue management, and automatic sync.
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
  useCallback,
  useRef,
} from 'react';
import { SGA_STORAGE_KEYS } from '@/lib/ativos/constants';
import type { SGAOfflineQueueItem } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

export type SyncStatus = 'idle' | 'syncing' | 'error' | 'offline';

interface OfflineSyncContextType {
  // Online status
  isOnline: boolean;

  // Queue state
  queue: SGAOfflineQueueItem[];
  queueLength: number;
  pendingCount: number;

  // Sync state
  syncStatus: SyncStatus;
  lastSyncAt: string | null;
  syncError: string | null;

  // Actions
  addToQueue: (action: string, payload: Record<string, unknown>) => string;
  removeFromQueue: (id: string) => void;
  clearQueue: () => void;
  retryItem: (id: string) => Promise<void>;
  syncAll: () => Promise<void>;

  // Auto-sync settings
  autoSyncEnabled: boolean;
  setAutoSyncEnabled: (enabled: boolean) => void;
  autoSyncInterval: number;
  setAutoSyncInterval: (ms: number) => void;
}

// =============================================================================
// Action Handlers (to be implemented)
// =============================================================================

type ActionHandler = (payload: Record<string, unknown>) => Promise<unknown>;

const actionHandlers: Record<string, ActionHandler> = {
  // Movement actions - these will call the service functions
  // For now, they're placeholders that will be wired up
  submit_count: async (payload) => {
    // Lazy import to avoid circular dependencies
    const { submitCount } = await import('@/services/sgaAgentcore');
    return submitCount(payload as unknown as Parameters<typeof submitCount>[0]);
  },
  create_reservation: async (payload) => {
    const { createReservation } = await import('@/services/sgaAgentcore');
    return createReservation(payload as unknown as Parameters<typeof createReservation>[0]);
  },
  process_expedition: async (payload) => {
    const { processExpedition } = await import('@/services/sgaAgentcore');
    return processExpedition(payload as unknown as Parameters<typeof processExpedition>[0]);
  },
  create_transfer: async (payload) => {
    const { createTransfer } = await import('@/services/sgaAgentcore');
    return createTransfer(payload as unknown as Parameters<typeof createTransfer>[0]);
  },
  process_return: async (payload) => {
    const { processReturn } = await import('@/services/sgaAgentcore');
    return processReturn(payload as unknown as Parameters<typeof processReturn>[0]);
  },
};

// =============================================================================
// Context
// =============================================================================

const OfflineSyncContext = createContext<OfflineSyncContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface OfflineSyncProviderProps {
  children: ReactNode;
  initialAutoSync?: boolean;
  initialSyncInterval?: number;
}

const DEFAULT_SYNC_INTERVAL = 60000; // 1 minute
const MAX_RETRIES = 3;

export function OfflineSyncProvider({
  children,
  initialAutoSync = true,
  initialSyncInterval = DEFAULT_SYNC_INTERVAL,
}: OfflineSyncProviderProps) {
  // Online status
  const [isOnline, setIsOnline] = useState(
    typeof navigator !== 'undefined' ? navigator.onLine : true
  );

  // Queue state (persisted to localStorage)
  const [queue, setQueue] = useState<SGAOfflineQueueItem[]>(() => {
    if (typeof window === 'undefined') return [];
    try {
      const stored = localStorage.getItem(SGA_STORAGE_KEYS.OFFLINE_QUEUE);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('idle');
  const [lastSyncAt, setLastSyncAt] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  // Auto-sync settings
  const [autoSyncEnabled, setAutoSyncEnabled] = useState(initialAutoSync);
  const [autoSyncInterval, setAutoSyncInterval] = useState(initialSyncInterval);

  // Refs
  const syncIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isSyncingRef = useRef(false);

  // Derived state
  const queueLength = queue.length;
  const pendingCount = queue.filter(item => item.retries < MAX_RETRIES).length;

  // Persist queue to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(SGA_STORAGE_KEYS.OFFLINE_QUEUE, JSON.stringify(queue));
  }, [queue]);

  // Online/offline detection
  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setSyncStatus('idle');
    };

    const handleOffline = () => {
      setIsOnline(false);
      setSyncStatus('offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Generate unique ID
  const generateId = () => `offline-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // Add item to queue
  const addToQueue = useCallback((action: string, payload: Record<string, unknown>): string => {
    const id = generateId();
    const item: SGAOfflineQueueItem = {
      id,
      action,
      payload,
      created_at: new Date().toISOString(),
      retries: 0,
    };

    setQueue(prev => [...prev, item]);
    return id;
  }, []);

  // Remove item from queue
  const removeFromQueue = useCallback((id: string) => {
    setQueue(prev => prev.filter(item => item.id !== id));
  }, []);

  // Clear entire queue
  const clearQueue = useCallback(() => {
    setQueue([]);
    setSyncError(null);
  }, []);

  // Process single item
  const processItem = useCallback(async (item: SGAOfflineQueueItem): Promise<boolean> => {
    const handler = actionHandlers[item.action];
    if (!handler) {
      console.error(`[OfflineSync] Unknown action: ${item.action}`);
      return false;
    }

    try {
      await handler(item.payload);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`[OfflineSync] Failed to process ${item.action}:`, message);

      // Update retry count and error
      setQueue(prev =>
        prev.map(q =>
          q.id === item.id
            ? { ...q, retries: q.retries + 1, last_error: message }
            : q
        )
      );

      return false;
    }
  }, []);

  // Retry single item
  const retryItem = useCallback(async (id: string) => {
    const item = queue.find(q => q.id === id);
    if (!item) return;

    if (!isOnline) {
      setSyncError('Sem conexao com a internet');
      return;
    }

    const success = await processItem(item);
    if (success) {
      removeFromQueue(id);
    }
  }, [queue, isOnline, processItem, removeFromQueue]);

  // Sync all pending items
  const syncAll = useCallback(async () => {
    if (isSyncingRef.current) return;
    if (!isOnline) {
      setSyncStatus('offline');
      return;
    }

    const pendingItems = queue.filter(item => item.retries < MAX_RETRIES);
    if (pendingItems.length === 0) {
      setSyncStatus('idle');
      return;
    }

    isSyncingRef.current = true;
    setSyncStatus('syncing');
    setSyncError(null);

    let successCount = 0;
    let errorCount = 0;

    for (const item of pendingItems) {
      const success = await processItem(item);
      if (success) {
        removeFromQueue(item.id);
        successCount++;
      } else {
        errorCount++;
      }
    }

    isSyncingRef.current = false;
    setLastSyncAt(new Date().toISOString());

    if (errorCount > 0) {
      setSyncStatus('error');
      setSyncError(`${errorCount} item(s) falharam ao sincronizar`);
    } else {
      setSyncStatus('idle');
    }
  }, [queue, isOnline, processItem, removeFromQueue]);

  // Auto-sync setup
  useEffect(() => {
    if (syncIntervalRef.current) {
      clearInterval(syncIntervalRef.current);
      syncIntervalRef.current = null;
    }

    if (autoSyncEnabled && autoSyncInterval > 0 && isOnline) {
      syncIntervalRef.current = setInterval(() => {
        if (queue.length > 0) {
          syncAll();
        }
      }, autoSyncInterval);
    }

    return () => {
      if (syncIntervalRef.current) {
        clearInterval(syncIntervalRef.current);
      }
    };
  }, [autoSyncEnabled, autoSyncInterval, isOnline, queue.length, syncAll]);

  // Sync when coming back online
  useEffect(() => {
    if (isOnline && queue.length > 0 && autoSyncEnabled) {
      // Small delay to ensure connection is stable
      const timeout = setTimeout(syncAll, 2000);
      return () => clearTimeout(timeout);
    }
  }, [isOnline, queue.length, autoSyncEnabled, syncAll]);

  return (
    <OfflineSyncContext.Provider
      value={{
        isOnline,
        queue,
        queueLength,
        pendingCount,
        syncStatus,
        lastSyncAt,
        syncError,
        addToQueue,
        removeFromQueue,
        clearQueue,
        retryItem,
        syncAll,
        autoSyncEnabled,
        setAutoSyncEnabled,
        autoSyncInterval,
        setAutoSyncInterval,
      }}
    >
      {children}
    </OfflineSyncContext.Provider>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useOfflineSync() {
  const context = useContext(OfflineSyncContext);
  if (context === undefined) {
    throw new Error('useOfflineSync must be used within an OfflineSyncProvider');
  }
  return context;
}
