// =============================================================================
// Academy Hooks Barrel Export - Faiston Academy
// =============================================================================
// Re-exports all Academy hooks for convenient importing.
// =============================================================================

// Core AI Feature Hooks
export { useNexoAI, type ChatMessage } from './useNexoAI';
export { useFlashcards } from './useFlashcards';
export { useMindMap } from './useMindMap';
export { useReflection } from './useReflection';

// Content Generation Hooks
export {
  useAudioClass,
  type AudioClassSettings,
  type AudioClassData,
  type PlaybackRate,
} from './useAudioClass';
export {
  useSlideDeck,
  type SlideDeckData,
  type SlideDeckSettings,
  type SlideDeckHistoryItem,
} from './useSlideDeck';
export {
  useVideoClass,
  type VideoClassSettings,
  type VideoClassData,
  type VideoSlide,
  type VideoFormat,
  type VisualTheme,
} from './useVideoClass';
export {
  useExtraClass,
  type ExtraClassPhase,
  type VideoHistoryStatus,
  type VideoHistoryItem,
  type ExtraClassData,
  type ExtraClassProgress,
  type ExtraClassTimestamp,
} from './useExtraClass';

// UI Management Hooks
export { useFloatingPanel, type ResizeDirection } from './useFloatingPanel';

// Discovery Hooks
export {
  useYouTubeRecommendations,
  prefetchYouTubeRecommendations,
  type YouTubeRecommendation,
} from './useYouTubeRecommendations';

// Library Hook
export { useLibrary, type LibraryFile } from './useLibrary';
