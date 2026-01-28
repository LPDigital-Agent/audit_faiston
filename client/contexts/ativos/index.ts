// =============================================================================
// SGA Inventory Contexts - Index
// =============================================================================
// Re-exports all contexts for the SGA (Sistema de Gestao de Ativos) module.
// =============================================================================

export {
  AssetManagementProvider,
  useAssetManagement,
} from './AssetManagementContext';

export {
  InventoryOperationsProvider,
  useInventoryOperations,
} from './InventoryOperationsContext';

export {
  TaskInboxProvider,
  useTaskInbox,
} from './TaskInboxContext';

export {
  NexoEstoqueProvider,
  useNexoEstoque,
  type ChatMessage,
  type QuickAction,
} from './NexoEstoqueContext';

export {
  InventoryCountProvider,
  useInventoryCount,
  type CountingItem,
} from './InventoryCountContext';

export {
  OfflineSyncProvider,
  useOfflineSync,
  type SyncStatus,
} from './OfflineSyncContext';
