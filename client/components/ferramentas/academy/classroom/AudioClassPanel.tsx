// =============================================================================
// Audio Class Panel - Faiston Academy
// =============================================================================
// AI-generated podcast-style audio lessons with ElevenLabs TTS.
// Supports multiple hosts, voice selection, and playback controls.
// =============================================================================

'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Headphones,
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Sparkles,
  Volume2,
  Clock,
  MessageSquare,
  BookOpen,
  Loader2,
  Check,
  AudioWaveform,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useAcademyClassroom } from '@/contexts/AcademyClassroomContext';
import {
  useAudioClass,
  PLAYBACK_RATES,
  MODE_LABELS,
  VOICE_OPTIONS,
  type AudioMode,
  type PlaybackRate,
} from '@/hooks/academy/useAudioClass';

interface AudioClassPanelProps {
  episodeId: string;
  transcription?: string;
}

function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

const MODE_OPTIONS: Array<{
  value: AudioMode;
  label: string;
  description: string;
  icon: typeof BookOpen;
}> = [
  {
    value: 'deep_explanation',
    label: 'Explicacao Profunda',
    description: 'Exploracao detalhada dos conceitos com exemplos.',
    icon: BookOpen,
  },
  {
    value: 'debate',
    label: 'Debate',
    description: 'Ouca diferentes perspectivas sobre o tema.',
    icon: MessageSquare,
  },
  {
    value: 'summary',
    label: 'Resumo',
    description: 'Visao rapida dos pontos-chave.',
    icon: Clock,
  },
];

const EXAMPLE_CHIPS = [
  'Linguagem Simplificada',
  'Adicionar Humor',
  'Tom Formal',
  'Focar no Historico',
  'Usar Analogias',
];

const VOICE_AVATAR_COLORS: Record<string, string> = {
  Sarah: 'b6e3f4',
  Jessica: 'c0aede',
  Lily: 'd1d4f9',
  Eric: 'c1f4c5',
  Chris: 'c1e7f4',
  Brian: 'ffdfbf',
};

const getVoiceAvatarUrl = (name: string): string => {
  const bgColor = VOICE_AVATAR_COLORS[name] || 'e8e8e8';
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${name}&backgroundColor=${bgColor}`;
};

const getVoiceNameById = (voiceId: string): string | null => {
  const femaleVoice = VOICE_OPTIONS.female.find((v) => v.id === voiceId);
  if (femaleVoice) return femaleVoice.name;
  const maleVoice = VOICE_OPTIONS.male.find((v) => v.id === voiceId);
  if (maleVoice) return maleVoice.name;
  return null;
};

const PROGRESS_STEPS = [
  { threshold: 10, text: 'Analisando transcricao...' },
  { threshold: 30, text: 'Gerando roteiro com IA...' },
  { threshold: 70, text: 'Convertendo para audio (pode levar 2-3 min)...' },
  { threshold: 90, text: 'Finalizando e salvando...' },
  { threshold: 100, text: 'Concluido!' },
];

const MODE_ESTIMATED_TIME: Record<string, string> = {
  summary: '1-2 minutos',
  debate: '2-3 minutos',
  deep_explanation: '2-4 minutos',
};

const getStepInfo = (progress: number) => {
  for (let i = 0; i < PROGRESS_STEPS.length; i++) {
    if (progress < PROGRESS_STEPS[i].threshold) {
      return { step: i + 1, ...PROGRESS_STEPS[i] };
    }
  }
  return { step: 5, threshold: 100, text: 'Concluido!' };
};

export function AudioClassPanel({ episodeId }: AudioClassPanelProps) {
  const {
    courseId,
    setAudioReady,
    audioGenerating,
    audioProgress,
    audioData,
    setAudioData,
    audioError,
    setAudioError,
    generateAudioClass,
  } = useAcademyClassroom();

  const [view, setView] = useState<'settings' | 'player' | 'completed'>('settings');
  const [transcription, setTranscription] = useState<string>('');
  const [loadingTranscription, setLoadingTranscription] = useState(false);
  const [voiceTab, setVoiceTab] = useState<'female' | 'male'>('female');

  const {
    studentName,
    settings,
    updateSettings,
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    progress,
    play,
    togglePlay,
    seek,
    skipForward,
    skipBackward,
    setPlaybackRate,
    resetAudio,
    formatTime,
    modeLabel,
  } = useAudioClass({ courseId, episodeId });

  const isGenerating = audioGenerating;
  const generateError = audioError;
  const hasAudio = !!audioData;
  const generationProgress = audioProgress;

  useEffect(() => {
    const url = getTranscriptionPath(courseId, episodeId);
    setLoadingTranscription(true);
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load');
        return r.text();
      })
      .then((content) => {
        setTranscription(content);
        setLoadingTranscription(false);
      })
      .catch(() => {
        setLoadingTranscription(false);
      });
  }, [courseId, episodeId]);

  useEffect(() => {
    if (hasAudio) {
      setView('player');
    }
  }, [hasAudio]);

  const [wasGenerating, setWasGenerating] = useState(false);
  useEffect(() => {
    if (wasGenerating && !isGenerating && hasAudio && !generateError) {
      setAudioReady(true);
    }
    setWasGenerating(isGenerating);
  }, [isGenerating, hasAudio, generateError, setAudioReady, wasGenerating]);

  useEffect(() => {
    setAudioReady(false);
  }, [setAudioReady]);

  const handleGenerate = () => {
    if (transcription) {
      const maleVoiceName = getVoiceNameById(settings.maleVoiceId) || 'Eric';
      const femaleVoiceName = getVoiceNameById(settings.femaleVoiceId) || 'Sarah';
      generateAudioClass(
        transcription,
        settings.mode,
        studentName,
        settings.customPrompt,
        settings.maleVoiceId,
        settings.femaleVoiceId,
        maleVoiceName,
        femaleVoiceName
      );
    }
  };

  const handleStartOver = () => {
    resetAudio();
    setAudioData(null);
    setAudioError(null);
    setView('settings');
  };

  const handleReplay = () => {
    seek(0);
    play();
  };

  const handleProgressChange = (value: number[]) => {
    const newTime = (value[0] / 100) * duration;
    seek(newTime);
  };

  const handleVoiceSelect = (voiceId: string, tab: 'female' | 'male') => {
    if (tab === 'female') {
      updateSettings({ femaleVoiceId: voiceId });
    } else {
      updateSettings({ maleVoiceId: voiceId });
    }
  };

  // Settings View
  if (view === 'settings') {
    return (
      <div className="h-full flex flex-col bg-black/20">
        <div className="px-6 py-4 border-b border-white/10">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Headphones className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Audio Class</h3>
              <p className="text-xs text-white/40">Crie e personalize sua experiencia de aprendizado.</p>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-6 space-y-6">
            {/* Mode Selector */}
            <div className="grid grid-cols-3 gap-3">
              {MODE_OPTIONS.map((option) => {
                const Icon = option.icon;
                const isSelected = settings.mode === option.value;
                return (
                  <button
                    key={option.value}
                    onClick={() => updateSettings({ mode: option.value })}
                    className={`relative p-4 rounded-xl border-2 transition-all duration-200 text-center ${
                      isSelected
                        ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/10 border-[var(--faiston-magenta-mid,#C31B8C)]/40'
                        : 'bg-white/[0.02] border-white/5 hover:border-white/10 hover:bg-white/[0.04]'
                    }`}
                  >
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-[var(--faiston-magenta-mid,#C31B8C)] flex items-center justify-center">
                        <Check className="w-3 h-3 text-white" />
                      </div>
                    )}
                    <div
                      className={`mx-auto mb-2 w-10 h-10 rounded-xl flex items-center justify-center ${
                        isSelected ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20' : 'bg-white/5'
                      }`}
                    >
                      <Icon
                        className={`w-5 h-5 ${isSelected ? 'text-[var(--faiston-magenta-mid,#C31B8C)]' : 'text-white/40'}`}
                      />
                    </div>
                    <h4
                      className={`font-semibold mb-1 text-sm ${isSelected ? 'text-[var(--faiston-magenta-mid,#C31B8C)]' : 'text-white'}`}
                    >
                      {option.label}
                    </h4>
                    <p className="text-xs text-white/40 leading-relaxed">{option.description}</p>
                  </button>
                );
              })}
            </div>

            {/* Voice Selection & Instructions */}
            <div className="grid grid-cols-[260px_1fr] gap-5">
              <div className="space-y-3">
                <div className="flex gap-2 p-1 bg-white/5 rounded-xl">
                  <button
                    onClick={() => setVoiceTab('female')}
                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
                      voiceTab === 'female'
                        ? 'bg-white/10 text-white shadow-sm'
                        : 'text-white/40 hover:text-white/60'
                    }`}
                  >
                    Feminino
                  </button>
                  <button
                    onClick={() => setVoiceTab('male')}
                    className={`flex-1 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
                      voiceTab === 'male'
                        ? 'bg-white/10 text-white shadow-sm'
                        : 'text-white/40 hover:text-white/60'
                    }`}
                  >
                    Masculino
                  </button>
                </div>
                <div className="space-y-2">
                  {VOICE_OPTIONS[voiceTab].map((voice) => {
                    const isSelected =
                      voiceTab === 'female'
                        ? settings.femaleVoiceId === voice.id
                        : settings.maleVoiceId === voice.id;
                    return (
                      <button
                        key={voice.id}
                        onClick={() => handleVoiceSelect(voice.id, voiceTab)}
                        className={`w-full flex items-center gap-3 p-2.5 rounded-xl border transition-all ${
                          isSelected
                            ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/10 border-[var(--faiston-magenta-mid,#C31B8C)]/30'
                            : 'bg-white/[0.02] border-transparent hover:bg-white/[0.04] hover:border-white/5'
                        }`}
                      >
                        <img
                          src={getVoiceAvatarUrl(voice.name)}
                          alt={voice.name}
                          className="w-9 h-9 rounded-full object-cover shrink-0"
                        />
                        <div className="flex-1 text-left min-w-0">
                          <div
                            className={`font-medium text-sm ${isSelected ? 'text-[var(--faiston-magenta-mid,#C31B8C)]' : 'text-white'}`}
                          >
                            {voice.name}
                          </div>
                          <div className="text-xs text-white/40 truncate">{voice.description}</div>
                        </div>
                        {isSelected && (
                          <div className="w-2 h-2 rounded-full bg-[var(--faiston-magenta-mid,#C31B8C)] shrink-0" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-white/60 mb-2">
                    Instrucoes Personalizadas
                  </label>
                  <Textarea
                    value={settings.customPrompt}
                    onChange={(e) => updateSettings({ customPrompt: e.target.value })}
                    placeholder="Forneca detalhes especificos, tom, ou pontos a cobrir..."
                    className="bg-white/[0.03] border-white/10 text-white placeholder:text-white/20 resize-none h-20 text-sm rounded-xl focus:border-[var(--faiston-magenta-mid,#C31B8C)]/50 focus:ring-1 focus:ring-[var(--faiston-magenta-mid,#C31B8C)]/20"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-white/60 mb-1.5">Sugestoes</label>
                  <div className="flex flex-wrap gap-1.5">
                    {EXAMPLE_CHIPS.map((chip) => (
                      <button
                        key={chip}
                        onClick={() => updateSettings({ customPrompt: chip })}
                        className="px-2.5 py-1 rounded-full text-xs bg-white/5 text-white/50 border border-white/10 hover:bg-white/10 hover:text-white/70 transition-all"
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {generateError && (
              <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                <p className="font-medium">Falha na geracao</p>
                <p className="text-xs opacity-70 mt-1">{generateError}</p>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-white/5">
          {isGenerating ? (
            <div className="space-y-3">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-[var(--faiston-magenta-mid,#C31B8C)] animate-pulse">
                  {getStepInfo(generationProgress).text}
                </span>
                <span className="text-white/40">{Math.round(generationProgress)}%</span>
              </div>
              <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: '0%' }}
                  animate={{ width: `${generationProgress}%` }}
                  transition={{ duration: 0.5 }}
                  className="h-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)]"
                />
              </div>
            </div>
          ) : (
            <Button
              onClick={handleGenerate}
              disabled={loadingTranscription || !transcription}
              className="w-full h-12 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white font-semibold rounded-xl border-0 transition-all"
            >
              Gerar Audio Class
              <AudioWaveform className="w-5 h-5 ml-2" />
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Player View
  return (
    <div className="h-full flex flex-col bg-black/20">
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Headphones className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          <span className="text-sm font-medium text-white/80">Audio Class</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/40">{modeLabel.label}</span>
          <button
            onClick={handleStartOver}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white/80 transition-all"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col p-6">
        <div className="flex-1 flex items-center justify-center">
          <motion.div
            animate={{ scale: isPlaying ? [1, 1.02, 1] : 1 }}
            transition={{ duration: 2, repeat: isPlaying ? Infinity : 0, ease: 'easeInOut' }}
            className="w-40 h-40 rounded-2xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 border border-[var(--faiston-magenta-mid,#C31B8C)]/30 flex items-center justify-center relative overflow-hidden"
          >
            <Headphones className="w-16 h-16 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          </motion.div>
        </div>

        <div className="text-center py-4">
          <h3 className="text-lg font-semibold text-white mb-1">Audio Class para {studentName}</h3>
          <p className="text-sm text-white/50">{modeLabel.description}</p>
        </div>

        <div className="w-full mb-6">
          <Slider
            value={[progress]}
            onValueChange={handleProgressChange}
            max={100}
            step={0.1}
            className="w-full"
          />
          <div className="flex items-center justify-between text-xs text-white/40 mt-2">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>
        </div>

        <div className="flex items-center justify-center gap-6 mb-6">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => skipBackward(10)}
            className="text-white/60 hover:text-white hover:bg-white/10"
          >
            <SkipBack className="w-5 h-5" />
          </Button>

          <Button
            onClick={togglePlay}
            size="lg"
            className="w-16 h-16 rounded-full bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white border-0"
          >
            {isPlaying ? <Pause className="w-7 h-7" /> : <Play className="w-7 h-7 ml-1" />}
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => skipForward(10)}
            className="text-white/60 hover:text-white hover:bg-white/10"
          >
            <SkipForward className="w-5 h-5" />
          </Button>
        </div>

        <div className="flex items-center justify-center gap-2">
          <span className="text-xs text-white/40">Velocidade:</span>
          <div className="flex gap-1">
            {PLAYBACK_RATES.map((rate) => (
              <button
                key={rate}
                onClick={() => setPlaybackRate(rate as PlaybackRate)}
                className={`px-2.5 py-1.5 rounded text-xs font-medium transition-all ${
                  playbackRate === rate
                    ? 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20 text-[var(--faiston-magenta-mid,#C31B8C)] border border-[var(--faiston-magenta-mid,#C31B8C)]/30'
                    : 'bg-white/5 text-white/60 border border-white/10 hover:bg-white/10'
                }`}
              >
                {rate}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
