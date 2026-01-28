// =============================================================================
// Academy Classroom Context - Faiston Academy
// =============================================================================
// Context for managing classroom state including:
// - Floating panel positions, sizes, and visibility
// - Notes persistence
// - Audio class background generation
// - Notification states
//
// AI Assistant: NEXO
// Platform: Faiston One
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
import { generateAudioClass as agentCoreGenerateAudioClass } from '@/services/academyAgentcore';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';
import type { ClassroomPanelId } from '@/lib/academy/constants';

// =============================================================================
// Types
// =============================================================================

export interface PanelState {
  position: { x: number; y: number };
  size: { width: number; height: number };
  isVisible: boolean;
  isMinimized: boolean;
  isMaximized: boolean;
  zIndex: number;
  preMaximizeState?: {
    position: { x: number; y: number };
    size: { width: number; height: number };
  };
}

export interface AudioClassData {
  audioBase64: string;
  audioUrl?: string;
  durationSeconds: number;
  mode: string;
  studentName: string;
  generatedAt: string;
}

interface AcademyClassroomContextType {
  // Panel states
  panels: Record<ClassroomPanelId, PanelState>;
  activePanel: ClassroomPanelId | null;

  // Panel actions
  updatePanelPosition: (id: ClassroomPanelId, position: { x: number; y: number }) => void;
  updatePanelSize: (id: ClassroomPanelId, size: { width: number; height: number }) => void;
  togglePanelVisibility: (id: ClassroomPanelId) => void;
  minimizePanel: (id: ClassroomPanelId) => void;
  maximizePanel: (id: ClassroomPanelId) => void;
  bringToFront: (id: ClassroomPanelId) => void;
  resetLayout: () => void;

  // Notes state
  notes: string;
  updateNotes: (notes: string) => void;
  notesSaving: boolean;

  // Audio Class notification state
  audioReady: boolean;
  setAudioReady: (ready: boolean) => void;

  // Extra Class (HeyGen video) notification state
  extraclassReady: boolean;
  setExtraclassReady: (ready: boolean) => void;

  // Audio Class generation state
  audioGenerating: boolean;
  setAudioGenerating: (generating: boolean) => void;
  audioProgress: number;
  setAudioProgress: (progress: number) => void;

  // Audio Class background generation
  audioData: AudioClassData | null;
  setAudioData: (data: AudioClassData | null) => void;
  audioError: string | null;
  setAudioError: (error: string | null) => void;
  generateAudioClass: (
    transcription: string,
    mode: string,
    studentName: string,
    customPrompt?: string,
    maleVoiceId?: string,
    femaleVoiceId?: string,
    maleVoiceName?: string,
    femaleVoiceName?: string
  ) => void;

  // Episode info
  courseId: string;
  episodeId: string;
  episodeTitle: string | null;
  courseCategory: string | null;
}

// =============================================================================
// Default Panel Configurations
// =============================================================================

const DEFAULT_PANELS: Record<ClassroomPanelId, PanelState> = {
  video: {
    position: { x: 40, y: 80 },
    size: { width: 800, height: 500 },
    isVisible: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 100,
  },
  transcription: {
    position: { x: 40, y: 600 },
    size: { width: 760, height: 280 },
    isVisible: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 101,
  },
  nexo: {
    position: { x: 860, y: 500 },
    size: { width: 350, height: 380 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 102,
  },
  flashcards: {
    position: { x: 900, y: 100 },
    size: { width: 420, height: 800 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 103,
  },
  mindmap: {
    position: { x: 850, y: 80 },
    size: { width: 800, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 104,
  },
  audioclass: {
    position: { x: 200, y: 30 },
    size: { width: 1100, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 105,
  },
  slidedeck: {
    position: { x: 200, y: 60 },
    size: { width: 850, height: 680 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 106,
  },
  library: {
    position: { x: 900, y: 80 },
    size: { width: 750, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 107,
  },
  notes: {
    position: { x: 860, y: 80 },
    size: { width: 350, height: 400 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 108,
  },
  extraclass: {
    position: { x: 100, y: 40 },
    size: { width: 1400, height: 800 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 109,
  },
  videoclass: {
    position: { x: 200, y: 30 },
    size: { width: 1100, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 110,
  },
  reflection: {
    position: { x: 300, y: 150 },
    size: { width: 600, height: 500 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 111,
  },
};

// Min sizes for each panel
export const PANEL_MIN_SIZES: Record<ClassroomPanelId, { width: number; height: number }> = {
  video: { width: 400, height: 300 },
  transcription: { width: 400, height: 200 },
  nexo: { width: 300, height: 300 },
  flashcards: { width: 420, height: 800 },
  mindmap: { width: 500, height: 500 },
  audioclass: { width: 1100, height: 700 },
  slidedeck: { width: 700, height: 550 },
  library: { width: 600, height: 500 },
  notes: { width: 280, height: 200 },
  extraclass: { width: 1200, height: 700 },
  videoclass: { width: 900, height: 600 },
  reflection: { width: 500, height: 400 },
};

// Panels with fixed sizes (non-resizable)
const FIXED_SIZE_PANELS: ClassroomPanelId[] = ['flashcards', 'audioclass', 'videoclass'];

// =============================================================================
// Context
// =============================================================================

const AcademyClassroomContext = createContext<AcademyClassroomContextType | undefined>(
  undefined
);

// =============================================================================
// Provider
// =============================================================================

interface AcademyClassroomProviderProps {
  children: ReactNode;
  courseId: string;
  episodeId: string;
  episodeTitle?: string | null;
  courseCategory?: string | null;
}

export function AcademyClassroomProvider({
  children,
  courseId,
  episodeId,
  episodeTitle = null,
  courseCategory = null,
}: AcademyClassroomProviderProps) {
  const [, setZIndexCounter] = useState(112);

  // Panel states - load from localStorage or use defaults (per-episode)
  const [panels, setPanels] = useState<Record<ClassroomPanelId, PanelState>>(() => {
    if (typeof window === 'undefined') return DEFAULT_PANELS;

    const storageKey = `${ACADEMY_STORAGE_KEYS.PROGRESS_PREFIX}layout_${courseId}_${episodeId}`;
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        const savedPanels = JSON.parse(stored);
        const merged = { ...DEFAULT_PANELS, ...savedPanels };
        FIXED_SIZE_PANELS.forEach((panelId) => {
          if (merged[panelId] && DEFAULT_PANELS[panelId]) {
            merged[panelId].size = DEFAULT_PANELS[panelId].size;
          }
        });
        return merged;
      } catch {
        return DEFAULT_PANELS;
      }
    }
    return DEFAULT_PANELS;
  });

  const [activePanel, setActivePanel] = useState<ClassroomPanelId | null>(null);

  // Notes state
  const [notes, setNotes] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    const notesKey = `${ACADEMY_STORAGE_KEYS.NOTES_PREFIX}${courseId}_${episodeId}`;
    return localStorage.getItem(notesKey) || '';
  });
  const [notesSaving, setNotesSaving] = useState(false);

  // Audio Class notification state
  const [audioReady, setAudioReady] = useState(false);
  const [extraclassReady, setExtraclassReady] = useState(false);

  // Audio Class generation state
  const [audioGenerating, setAudioGenerating] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioData, setAudioData] = useState<AudioClassData | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Persist panel layout to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const storageKey = `${ACADEMY_STORAGE_KEYS.PROGRESS_PREFIX}layout_${courseId}_${episodeId}`;
    localStorage.setItem(storageKey, JSON.stringify(panels));
  }, [panels, courseId, episodeId]);

  // Persist notes with debounce
  useEffect(() => {
    if (typeof window === 'undefined') return;
    setNotesSaving(true);
    const timeout = setTimeout(() => {
      const notesKey = `${ACADEMY_STORAGE_KEYS.NOTES_PREFIX}${courseId}_${episodeId}`;
      localStorage.setItem(notesKey, notes);
      setNotesSaving(false);
    }, 500);

    return () => clearTimeout(timeout);
  }, [notes, courseId, episodeId]);

  // Load notes when episode changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const notesKey = `${ACADEMY_STORAGE_KEYS.NOTES_PREFIX}${courseId}_${episodeId}`;
    const storedNotes = localStorage.getItem(notesKey);
    setNotes(storedNotes || '');
  }, [courseId, episodeId]);

  // Load panel layout when episode changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const storageKey = `${ACADEMY_STORAGE_KEYS.PROGRESS_PREFIX}layout_${courseId}_${episodeId}`;
    const stored = localStorage.getItem(storageKey);
    if (stored) {
      try {
        const savedPanels = JSON.parse(stored);
        const merged = { ...DEFAULT_PANELS, ...savedPanels };
        FIXED_SIZE_PANELS.forEach((panelId) => {
          if (merged[panelId] && DEFAULT_PANELS[panelId]) {
            merged[panelId].size = DEFAULT_PANELS[panelId].size;
          }
        });
        setPanels(merged);
      } catch {
        setPanels(DEFAULT_PANELS);
      }
    } else {
      setPanels(DEFAULT_PANELS);
    }
  }, [courseId, episodeId]);

  // Panel actions
  const updatePanelPosition = useCallback(
    (id: ClassroomPanelId, position: { x: number; y: number }) => {
      setPanels((prev) => ({
        ...prev,
        [id]: { ...prev[id], position },
      }));
    },
    []
  );

  const updatePanelSize = useCallback(
    (id: ClassroomPanelId, size: { width: number; height: number }) => {
      if (FIXED_SIZE_PANELS.includes(id)) {
        return;
      }
      const minSize = PANEL_MIN_SIZES[id] || { width: 200, height: 150 };
      setPanels((prev) => ({
        ...prev,
        [id]: {
          ...prev[id],
          size: {
            width: Math.max(size.width, minSize.width),
            height: Math.max(size.height, minSize.height),
          },
        },
      }));
    },
    []
  );

  const togglePanelVisibility = useCallback((id: ClassroomPanelId) => {
    setPanels((prev) => ({
      ...prev,
      [id]: { ...prev[id], isVisible: !prev[id].isVisible },
    }));
  }, []);

  const minimizePanel = useCallback((id: ClassroomPanelId) => {
    setPanels((prev) => ({
      ...prev,
      [id]: { ...prev[id], isMinimized: !prev[id].isMinimized },
    }));
  }, []);

  const maximizePanel = useCallback((id: ClassroomPanelId) => {
    setPanels((prev) => {
      const panel = prev[id];
      if (panel.isMaximized) {
        return {
          ...prev,
          [id]: {
            ...panel,
            isMaximized: false,
            position: panel.preMaximizeState?.position || panel.position,
            size: panel.preMaximizeState?.size || panel.size,
            preMaximizeState: undefined,
          },
        };
      } else {
        return {
          ...prev,
          [id]: {
            ...panel,
            isMaximized: true,
            preMaximizeState: {
              position: panel.position,
              size: panel.size,
            },
            position: { x: 40, y: 80 },
            size: {
              width: window.innerWidth - 80,
              height: window.innerHeight - 160,
            },
          },
        };
      }
    });
  }, []);

  const bringToFront = useCallback((id: ClassroomPanelId) => {
    setActivePanel(id);
    setZIndexCounter((prev) => {
      const newZ = prev + 1;
      setPanels((p) => ({
        ...p,
        [id]: { ...p[id], zIndex: newZ },
      }));
      return newZ;
    });
  }, []);

  const resetLayout = useCallback(() => {
    setPanels(DEFAULT_PANELS);
    setZIndexCounter(112);
  }, []);

  // Audio Class background generation function
  const generateAudioClass = useCallback(
    async (
      transcription: string,
      mode: string,
      studentName: string,
      customPrompt?: string,
      maleVoiceId?: string,
      femaleVoiceId?: string,
      maleVoiceName?: string,
      femaleVoiceName?: string
    ) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }

      abortControllerRef.current = new AbortController();

      setAudioGenerating(true);
      setAudioProgress(0);
      setAudioError(null);
      setAudioData(null);

      let currentProgress = 0;
      progressIntervalRef.current = setInterval(() => {
        if (currentProgress >= 85) return;
        let increment: number;
        if (currentProgress < 30) {
          increment = 1.0;
        } else if (currentProgress < 70) {
          increment = 0.4;
        } else {
          increment = 0.15;
        }
        currentProgress = Math.min(currentProgress + increment, 85);
        setAudioProgress(currentProgress);
      }, 1000);

      try {
        const { data } = await agentCoreGenerateAudioClass(
          {
            transcription,
            mode: mode as 'deep_explanation' | 'debate' | 'summary',
            student_name: studentName,
            custom_prompt: customPrompt || undefined,
            male_voice_id: maleVoiceId,
            female_voice_id: femaleVoiceId,
            male_voice_name: maleVoiceName,
            female_voice_name: femaleVoiceName,
          },
          abortControllerRef.current.signal
        );

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const errorData = data as any;
        if (errorData.error) {
          const errorMessage = errorData.error_pt || String(errorData.error);
          setAudioError(errorMessage);
          return;
        }

        if (!data.audio_url && !data.audio_base64) {
          setAudioError('Nenhum dado de audio recebido do servidor');
          return;
        }

        const newAudioData: AudioClassData = {
          audioBase64: data.audio_base64 || '',
          audioUrl: data.audio_url || undefined,
          durationSeconds: data.duration_seconds || 0,
          mode: data.mode,
          studentName: data.student_name || studentName,
          generatedAt: new Date().toISOString(),
        };

        setAudioData(newAudioData);
        setAudioProgress(100);
        setAudioReady(true);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        let errorMessage = 'Falha ao gerar audio';
        if (err instanceof Error) {
          if (
            err.message.includes('Failed to fetch') ||
            err.message.includes('NetworkError')
          ) {
            errorMessage =
              'Conexao perdida. A geracao pode ter demorado muito. Tente o modo Resumo para um resultado mais rapido.';
          } else if (err.message.includes('timeout')) {
            errorMessage =
              'Tempo esgotado. Tente novamente ou use o modo Resumo para um resultado mais rapido.';
          } else {
            errorMessage = err.message;
          }
        }
        setAudioError(errorMessage);
      } finally {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setAudioGenerating(false);
      }
    },
    []
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);

  const updateNotes = useCallback((newNotes: string) => {
    setNotes(newNotes);
  }, []);

  return (
    <AcademyClassroomContext
      value={{
        panels,
        activePanel,
        updatePanelPosition,
        updatePanelSize,
        togglePanelVisibility,
        minimizePanel,
        maximizePanel,
        bringToFront,
        resetLayout,
        notes,
        updateNotes,
        notesSaving,
        audioReady,
        setAudioReady,
        extraclassReady,
        setExtraclassReady,
        audioGenerating,
        setAudioGenerating,
        audioProgress,
        setAudioProgress,
        audioData,
        setAudioData,
        audioError,
        setAudioError,
        generateAudioClass,
        courseId,
        episodeId,
        episodeTitle,
        courseCategory,
      }}
    >
      {children}
    </AcademyClassroomContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useAcademyClassroom() {
  const context = useContext(AcademyClassroomContext);
  if (context === undefined) {
    throw new Error(
      'useAcademyClassroom must be used within an AcademyClassroomProvider'
    );
  }
  return context;
}
