// =============================================================================
// useLibrary Hook - Faiston Academy
// =============================================================================
// Hook for managing library files and course materials.
// Supports PDF preview/download and external link management.
// =============================================================================


import { useState, useEffect, useCallback, useMemo } from 'react';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

export interface LibraryFile {
  id: string;
  name: string;
  type: 'pdf' | 'link';
  url: string;
  size?: number;
  description?: string;
  domain?: string;
  addedAt?: string;
}

interface LibraryState {
  files: LibraryFile[];
  isLoading: boolean;
  selectedFile: LibraryFile | null;
  isPreviewOpen: boolean;
}

const getStorageKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.LIBRARY_PREFIX ?? 'faiston_academy_library_'}${courseId}_${episodeId}`;

const getTranscriptionKey = (courseId: string, episodeId: string) =>
  `${ACADEMY_STORAGE_KEYS.TRANSCRIPTION_PREFIX ?? 'faiston_academy_transcription_'}${courseId}_${episodeId}`;

// Mock files for development (in production, would come from API)
const getMockFiles = (): LibraryFile[] => {
  // Return empty array - files would come from backend in production
  return [];
};

export function useLibrary(episodeId: string, courseId: string) {
  const [state, setState] = useState<LibraryState>({
    files: [],
    isLoading: true,
    selectedFile: null,
    isPreviewOpen: false,
  });

  const [transcription, setTranscription] = useState<string | undefined>(undefined);
  const [isLoadingTranscription, setIsLoadingTranscription] = useState(true);

  // Load files from localStorage on mount
  useEffect(() => {
    const loadData = async () => {
      setState((prev) => ({ ...prev, isLoading: true }));

      try {
        const storageKey = getStorageKey(courseId, episodeId);
        const stored = localStorage.getItem(storageKey);

        if (stored) {
          const parsed = JSON.parse(stored);
          setState({
            files: parsed.files || [],
            isLoading: false,
            selectedFile: null,
            isPreviewOpen: false,
          });
        } else {
          // Use mock files for now
          const mockFiles = getMockFiles();
          setState({
            files: mockFiles,
            isLoading: false,
            selectedFile: null,
            isPreviewOpen: false,
          });
        }
      } catch (e) {
        console.error('Failed to load library files:', e);
        setState({
          files: [],
          isLoading: false,
          selectedFile: null,
          isPreviewOpen: false,
        });
      }
    };

    loadData();
  }, [courseId, episodeId]);

  // Load transcription from localStorage
  useEffect(() => {
    const loadTranscription = async () => {
      setIsLoadingTranscription(true);

      try {
        const transcriptionKey = getTranscriptionKey(courseId, episodeId);
        const stored = localStorage.getItem(transcriptionKey);

        if (stored) {
          setTranscription(stored);
        } else {
          setTranscription(undefined);
        }
      } catch (e) {
        console.error('Failed to load transcription:', e);
        setTranscription(undefined);
      } finally {
        setIsLoadingTranscription(false);
      }
    };

    loadTranscription();
  }, [courseId, episodeId]);

  // Save files to localStorage when they change
  useEffect(() => {
    if (!state.isLoading && state.files.length > 0) {
      const storageKey = getStorageKey(courseId, episodeId);
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify({ files: state.files })
        );
      } catch (e) {
        console.error('Failed to save library files:', e);
      }
    }
  }, [state.files, state.isLoading, courseId, episodeId]);

  // Open file preview
  const openPreview = useCallback((file: LibraryFile) => {
    if (file.type === 'link') {
      // Open external links in new tab
      window.open(file.url, '_blank', 'noopener,noreferrer');
    } else {
      // Open PDF in preview modal
      setState((prev) => ({
        ...prev,
        selectedFile: file,
        isPreviewOpen: true,
      }));
    }
  }, []);

  // Close preview
  const closePreview = useCallback(() => {
    setState((prev) => ({
      ...prev,
      selectedFile: null,
      isPreviewOpen: false,
    }));
  }, []);

  // Download file
  const downloadFile = useCallback((file: LibraryFile) => {
    if (file.type === 'pdf' && file.url) {
      // Create download link
      const link = document.createElement('a');
      link.href = file.url;
      link.download = file.name;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }, []);

  // Add file to library
  const addFile = useCallback((file: Omit<LibraryFile, 'id' | 'addedAt'>) => {
    const newFile: LibraryFile = {
      ...file,
      id: `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      addedAt: new Date().toISOString(),
    };

    setState((prev) => ({
      ...prev,
      files: [...prev.files, newFile],
    }));

    return newFile;
  }, []);

  // Remove file from library
  const removeFile = useCallback((fileId: string) => {
    setState((prev) => ({
      ...prev,
      files: prev.files.filter((f) => f.id !== fileId),
    }));
  }, []);

  // File count
  const fileCount = useMemo(() => state.files.length, [state.files]);

  return {
    // State
    files: state.files,
    isLoading: state.isLoading,
    selectedFile: state.selectedFile,
    isPreviewOpen: state.isPreviewOpen,

    // Actions
    openPreview,
    closePreview,
    downloadFile,
    addFile,
    removeFile,

    // Helpers
    fileCount,

    // Transcription
    transcription,
    isLoadingTranscription,
  };
}
