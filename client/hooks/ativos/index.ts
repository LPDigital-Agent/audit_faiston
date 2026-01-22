// =============================================================================
// SGA Inventory Module - Hooks Index
// =============================================================================
// Central export for all SGA (Sistema de Gestão de Ativos) hooks.
// =============================================================================

// Asset hooks
export { useAssets } from './useAssets';
export type { SGAAssetFilters } from './useAssets';

export { useAssetDetail } from './useAssetDetail';

// Balance hook
export { useBalanceQuery } from './useBalanceQuery';

// Movement hooks
export { useMovements } from './useMovements';
export type { SGAMovementFilters } from './useMovements';

export { useMovementMutations } from './useMovementMutations';

export { useMovementValidation } from './useMovementValidation';
export type { SGAMovementType, ComplianceValidation } from './useMovementValidation';

// Master data hooks
export { useLocations } from './useLocations';
export type { SGALocation } from './useLocations';

export { usePartNumbers } from './usePartNumbers';
export type { SGAPartNumber } from './usePartNumbers';

export { useProjects } from './useProjects';
export type { SGAProject } from './useProjects';

// NF hook
export { useNFReader } from './useNFReader';
export type { NFExtraction, NFItemMapping, PendingNFEntry, ConfidenceScore } from './useNFReader';

// Bulk Import hook
export { useBulkImport } from './useBulkImport';
export type {
  ImportColumnMapping,
  ImportPreviewRow,
  SGAImportPreviewResponse,
  SGAImportExecuteResponse,
  SGAPNMappingValidationResponse,
} from './useBulkImport';

// Scanner hook
export { useSerialScanner } from './useSerialScanner';
export type { ScanMode, ScanResult } from './useSerialScanner';

// Image OCR hook
export { useImageOCR } from './useImageOCR';
export type { UseImageOCRReturn } from './useImageOCR';

// SAP Import hook
export { useSAPImport, SAP_EXPECTED_COLUMNS, SAP_COLUMN_LABELS } from './useSAPImport';
export type {
  SAPColumnMapping,
  SAPImportPreviewRow,
  SAPImportPreview,
  SAPImportResult,
  UseSAPImportReturn,
} from './useSAPImport';

// Manual Entry hook
export { useManualEntry } from './useManualEntry';
export type {
  ManualEntryItem,
  ManualEntryRequest,
  ManualEntryResult,
  UseManualEntryReturn,
} from './useManualEntry';

// Smart Import hook (Universal File Importer)
export {
  useSmartImporter,
  detectFileTypeFromFile,
  validateSmartImportFile,
  requiresHILReview,
  isNFImportResult,
  isSpreadsheetImportResult,
  isTextImportResult,
  getFileTypeLabel,
  SMART_IMPORT_FORMATS,
} from './useSmartImporter';
export type {
  SmartFileType,
  SmartSourceType,
  SmartImportPreview,
  SmartImportProgress,
  UseSmartImporterReturn,
  SmartImportUploadResponse,
  EnrichedError,  // BUG-027: Export for DebugAnalysisPanel integration
} from './useSmartImporter';

// Context-based hooks (re-exported from contexts for convenience)
export {
  useAssetManagement,
  useTaskInbox,
  useNexoEstoque,
  useInventoryOperations,
  useInventoryCount,
  useOfflineSync,
} from '@/contexts/ativos';
