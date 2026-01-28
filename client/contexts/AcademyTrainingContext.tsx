// =============================================================================
// Academy Training Context - Faiston Academy
// =============================================================================
// Context provider for NEXO Tutor custom training classrooms.
// Manages panel layout, notes, and AI feature state.
//
// Key Differences from AcademyClassroomContext:
// - Uses trainingId instead of courseId/episodeId
// - Uses consolidated_content as transcription source
// - ContentViewerPanel replaces VideoPlayerPanel
// - No episodes (single training unit)
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
  startTransition,
} from 'react';
import { generateAudioClass as agentCoreGenerateAudioClass } from '@/services/academyAgentcore';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

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

export interface CustomTraining {
  id: string;
  title: string;
  description?: string;
  consolidatedContent?: string;
  status: 'draft' | 'processing' | 'ready' | 'error';
  thumbnailUrl?: string;
  createdAt: string;
  updatedAt: string;
}

// Training panel IDs
export type TrainingPanelId =
  | 'contentviewer'
  | 'notes'
  | 'nexo'
  | 'transcription'
  | 'flashcards'
  | 'mindmap'
  | 'audioclass'
  | 'library'
  | 'slidedeck'
  | 'extraclass';

// =============================================================================
// Default Panel Configuration
// =============================================================================

// ContentViewer replaces Video for custom trainings
const DEFAULT_PANELS: Record<TrainingPanelId, PanelState> = {
  contentviewer: {
    position: { x: 40, y: 80 },
    size: { width: 800, height: 500 },
    isVisible: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 100,
  },
  notes: {
    position: { x: 860, y: 80 },
    size: { width: 350, height: 400 },
    isVisible: false,
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
  transcription: {
    position: { x: 40, y: 600 },
    size: { width: 760, height: 280 },
    isVisible: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 103,
  },
  flashcards: {
    position: { x: 900, y: 100 },
    size: { width: 420, height: 800 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 105,
  },
  mindmap: {
    position: { x: 850, y: 80 },
    size: { width: 800, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 106,
  },
  audioclass: {
    position: { x: 200, y: 30 },
    size: { width: 1100, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 107,
  },
  library: {
    position: { x: 900, y: 80 },
    size: { width: 750, height: 700 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 108,
  },
  slidedeck: {
    position: { x: 200, y: 60 },
    size: { width: 850, height: 680 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 111,
  },
  extraclass: {
    position: { x: 100, y: 40 },
    size: { width: 1400, height: 800 },
    isVisible: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 112,
  },
};

export const TRAINING_PANEL_MIN_SIZES: Record<TrainingPanelId, { width: number; height: number }> = {
  contentviewer: { width: 500, height: 400 },
  notes: { width: 280, height: 200 },
  nexo: { width: 300, height: 300 },
  transcription: { width: 400, height: 200 },
  flashcards: { width: 420, height: 800 },
  mindmap: { width: 500, height: 500 },
  audioclass: { width: 1100, height: 700 },
  library: { width: 600, height: 500 },
  slidedeck: { width: 700, height: 550 },
  extraclass: { width: 1200, height: 700 },
};

// Panels that cannot be resized
const FIXED_SIZE_PANELS: TrainingPanelId[] = ['flashcards', 'audioclass'];

// =============================================================================
// Context Type
// =============================================================================

interface AcademyTrainingContextType {
  // Training data
  training: CustomTraining | null;
  trainingId: string;
  transcription: string;

  // Panel states
  panels: Record<TrainingPanelId, PanelState>;
  activePanel: TrainingPanelId | null;

  // Panel actions
  updatePanelPosition: (id: TrainingPanelId, position: { x: number; y: number }) => void;
  updatePanelSize: (id: TrainingPanelId, size: { width: number; height: number }) => void;
  togglePanelVisibility: (id: TrainingPanelId) => void;
  minimizePanel: (id: TrainingPanelId) => void;
  maximizePanel: (id: TrainingPanelId) => void;
  bringToFront: (id: TrainingPanelId) => void;
  resetLayout: () => void;

  // Notes state
  notes: string;
  updateNotes: (notes: string) => void;
  notesSaving: boolean;

  // Audio Class notification state
  audioReady: boolean;
  setAudioReady: (ready: boolean) => void;

  // Extra Class notification state
  extraclassReady: boolean;
  setExtraclassReady: (ready: boolean) => void;

  // Audio Class generation state
  audioGenerating: boolean;
  setAudioGenerating: (generating: boolean) => void;
  audioProgress: number;
  setAudioProgress: (progress: number) => void;
  audioData: AudioClassData | null;
  setAudioData: (data: AudioClassData | null) => void;
  audioError: string | null;
  setAudioError: (error: string | null) => void;
  generateAudioClass: (
    mode: string,
    studentName: string,
    customPrompt?: string,
    maleVoiceId?: string,
    femaleVoiceId?: string,
    maleVoiceName?: string,
    femaleVoiceName?: string
  ) => void;
}

const AcademyTrainingContext = createContext<AcademyTrainingContextType | undefined>(undefined);

// =============================================================================
// Provider Component
// =============================================================================

interface AcademyTrainingProviderProps {
  children: ReactNode;
  trainingId: string;
  training: CustomTraining | null;
}

export function AcademyTrainingProvider({
  children,
  trainingId,
  training,
}: AcademyTrainingProviderProps) {
  // Z-index counter for panel ordering
  const [, setZIndexCounter] = useState(113);

  // Panel states - load from localStorage or use defaults
  const [panels, setPanels] = useState<Record<TrainingPanelId, PanelState>>(() => {
    if (typeof window === 'undefined') return DEFAULT_PANELS;

    const storageKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}layout_${trainingId}`;
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

  // Active panel
  const [activePanel, setActivePanel] = useState<TrainingPanelId | null>(null);

  // Notes state
  const [notes, setNotes] = useState<string>(() => {
    if (typeof window === 'undefined') return '';
    const notesKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}notes_${trainingId}`;
    return localStorage.getItem(notesKey) || '';
  });
  const [notesSaving, setNotesSaving] = useState(false);

  // Audio Class states
  const [audioReady, setAudioReady] = useState(false);
  const [extraclassReady, setExtraclassReady] = useState(false);
  const [audioGenerating, setAudioGenerating] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioData, setAudioData] = useState<AudioClassData | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Transcription from consolidated content
  const transcription = training?.consolidatedContent || '';

  // =============================================================================
  // Effects
  // =============================================================================

  // Persist panel layout
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const storageKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}layout_${trainingId}`;
    localStorage.setItem(storageKey, JSON.stringify(panels));
  }, [panels, trainingId]);

  // Persist notes with debounce
  useEffect(() => {
    if (typeof window === 'undefined') return;
    startTransition(() => {
      setNotesSaving(true);
    });
    const timeout = setTimeout(() => {
      const notesKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}notes_${trainingId}`;
      localStorage.setItem(notesKey, notes);
      startTransition(() => {
        setNotesSaving(false);
      });
    }, 500);
    return () => clearTimeout(timeout);
  }, [notes, trainingId]);

  // Load notes when training changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const notesKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}notes_${trainingId}`;
    const storedNotes = localStorage.getItem(notesKey);
    startTransition(() => {
      setNotes(storedNotes || '');
    });
  }, [trainingId]);

  // Load panel layout when training changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const storageKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}layout_${trainingId}`;
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
        startTransition(() => {
          setPanels(merged);
        });
      } catch {
        startTransition(() => {
          setPanels(DEFAULT_PANELS);
        });
      }
    } else {
      startTransition(() => {
        setPanels(DEFAULT_PANELS);
      });
    }
  }, [trainingId]);

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

  // =============================================================================
  // Panel Actions
  // =============================================================================

  const updatePanelPosition = useCallback(
    (id: TrainingPanelId, position: { x: number; y: number }) => {
      setPanels((prev) => ({
        ...prev,
        [id]: { ...prev[id], position },
      }));
    },
    []
  );

  const updatePanelSize = useCallback(
    (id: TrainingPanelId, size: { width: number; height: number }) => {
      if (FIXED_SIZE_PANELS.includes(id)) return;
      const minSize = TRAINING_PANEL_MIN_SIZES[id] || { width: 200, height: 150 };
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

  const togglePanelVisibility = useCallback((id: TrainingPanelId) => {
    setPanels((prev) => ({
      ...prev,
      [id]: { ...prev[id], isVisible: !prev[id].isVisible },
    }));
  }, []);

  const minimizePanel = useCallback((id: TrainingPanelId) => {
    setPanels((prev) => ({
      ...prev,
      [id]: { ...prev[id], isMinimized: !prev[id].isMinimized },
    }));
  }, []);

  const maximizePanel = useCallback((id: TrainingPanelId) => {
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

  const bringToFront = useCallback((id: TrainingPanelId) => {
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
    if (typeof window !== 'undefined') {
      const storageKey = `${ACADEMY_STORAGE_KEYS.TRAINING_PREFIX}layout_${trainingId}`;
      localStorage.removeItem(storageKey);
    }
  }, [trainingId]);

  // =============================================================================
  // Audio Class Generation
  // =============================================================================

  const generateAudioClass = useCallback(
    (
      mode: string,
      studentName: string,
      customPrompt?: string,
      maleVoiceId?: string,
      femaleVoiceId?: string,
      maleVoiceName?: string,
      femaleVoiceName?: string
    ) => {
      if (!transcription) {
        setAudioError('Conteudo do treinamento nao disponivel');
        return;
      }

      // Cancel previous request if any
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }

      // Setup new request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setAudioGenerating(true);
      setAudioProgress(0);
      setAudioError(null);
      setAudioData(null);

      // Simulate progress while waiting
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

      // Make API call
      agentCoreGenerateAudioClass(
        {
          transcription,
          mode: mode as 'deep_explanation' | 'debate' | 'summary',
          student_name: studentName,
          custom_prompt: customPrompt,
          male_voice_id: maleVoiceId,
          female_voice_id: femaleVoiceId,
          male_voice_name: maleVoiceName,
          female_voice_name: femaleVoiceName,
        },
        abortController.signal
      )
        .then((response) => {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
          }

          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const errorData = response.data as any;
          if (errorData.error) {
            const errorMessage = errorData.error_pt || String(errorData.error);
            setAudioError(errorMessage);
            setAudioGenerating(false);
            return;
          }

          setAudioProgress(100);
          setAudioData({
            audioBase64: response.data.audio_base64 || '',
            audioUrl: response.data.audio_url,
            durationSeconds: response.data.duration_seconds,
            mode: response.data.mode,
            studentName: response.data.student_name,
            generatedAt: new Date().toISOString(),
          });
          setAudioGenerating(false);
          setAudioReady(true);
        })
        .catch((error) => {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
          }
          if (error.name !== 'AbortError') {
            let errorMessage = 'Falha ao gerar audio';
            if (error instanceof Error) {
              if (
                error.message.includes('Failed to fetch') ||
                error.message.includes('NetworkError')
              ) {
                errorMessage =
                  'Conexao perdida. A geracao pode ter demorado muito. Tente o modo Resumo para um resultado mais rapido.';
              } else if (error.message.includes('timeout')) {
                errorMessage =
                  'Tempo esgotado. Tente novamente ou use o modo Resumo para um resultado mais rapido.';
              } else {
                errorMessage = error.message;
              }
            }
            setAudioError(errorMessage);
            setAudioGenerating(false);
          }
        });
    },
    [transcription]
  );

  const updateNotes = useCallback((newNotes: string) => {
    setNotes(newNotes);
  }, []);

  // =============================================================================
  // Context Value
  // =============================================================================

  const value: AcademyTrainingContextType = {
    training,
    trainingId,
    transcription,
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
  };

  return (
    <AcademyTrainingContext value={value}>
      {children}
    </AcademyTrainingContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useAcademyTraining() {
  const context = useContext(AcademyTrainingContext);
  if (context === undefined) {
    throw new Error(
      'useAcademyTraining must be used within an AcademyTrainingProvider'
    );
  }
  return context;
}
