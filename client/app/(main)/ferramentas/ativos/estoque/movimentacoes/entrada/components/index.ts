// =============================================================================
// Entrada Components Index
// =============================================================================
// Barrel export for all entrada tab components.
// =============================================================================

// NEW: Smart Import Components (Universal File Importer)
export { SmartUploadZone } from './SmartUploadZone';
export { SmartPreview } from './SmartPreview';

// Preview Components
export { NFPreview, SpreadsheetPreview, TextPreview } from './previews';

// Active Components
export { EntradaManualTab } from './EntradaManualTab';
export { PendingEntriesList } from './PendingEntriesList';

// DEPRECATED: Legacy tab components (kept for reference, not used in new design)
// These have been replaced by SmartUploadZone which handles all file types
export { EntradaNFTab } from './EntradaNFTab';
export { EntradaImagemTab } from './EntradaImagemTab';
export { EntradaSAPTab } from './EntradaSAPTab';
