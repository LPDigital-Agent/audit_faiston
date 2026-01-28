// =============================================================================
// Reflection Modal - Faiston Academy
// =============================================================================
// Learning reflection modal for student self-assessment.
// Students explain what they learned and receive AI-powered feedback.
// =============================================================================

'use client';

import { useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  MessageCircle,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  Sparkles,
  Play,
} from 'lucide-react';
import { useReflection, type ProximoPasso } from '@/hooks/academy/useReflection';
import { formatTimestamp } from '@/lib/utils';

interface ReflectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
  transcription: string;
  episodeTitle: string;
  courseId: string;
  episodeId: string;
  onSeekToTimestamp?: (time: number) => void;
}

// Score color helper
function getScoreColorClass(score: number) {
  if (score >= 70) return 'text-green-400';
  if (score >= 50) return 'text-yellow-400';
  return 'text-orange-400';
}

function getScoreBgClass(score: number) {
  if (score >= 70) return 'from-green-500/20 to-green-600/10 border-green-500/30';
  if (score >= 50) return 'from-yellow-500/20 to-yellow-600/10 border-yellow-500/30';
  return 'from-orange-500/20 to-orange-600/10 border-orange-500/30';
}

export function ReflectionModal({
  isOpen,
  onClose,
  onComplete,
  transcription,
  courseId,
  episodeId,
  onSeekToTimestamp,
}: ReflectionModalProps) {
  const {
    explanation,
    setExplanation,
    analysis,
    charCount,
    wordCount,
    isValidLength,
    minChars,
    maxChars,
    submit,
    retry,
    isAnalyzing,
    analyzeError,
    canSubmit,
    canRetry,
    remainingAttempts,
    hasAnalysis,
  } = useReflection({
    courseId,
    episodeId,
    onSeek: onSeekToTimestamp,
  });

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      retry();
    }
  }, [isOpen, retry]);

  const handleSubmit = () => {
    submit(transcription);
  };

  const handleContinue = () => {
    onComplete();
    onClose();
  };

  const handleRetry = () => {
    retry();
  };

  // Handler for timestamp click: close modal and seek video
  const handleSeekAndClose = useCallback(
    (time: number) => {
      onSeekToTimestamp?.(time);
      onClose();
    },
    [onSeekToTimestamp, onClose]
  );

  // Determine current view
  const view = isAnalyzing ? 'loading' : hasAnalysis ? 'results' : 'input';

  return (
    <Dialog open={isOpen} onOpenChange={() => {}}>
      <DialogContent
        className="bg-black/20 max-w-2xl border-[var(--faiston-magenta-mid,#C31B8C)] border-2 text-white p-0 overflow-hidden rounded-[32px]"
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <AnimatePresence mode="wait">
          {view === 'input' && (
            <InputView
              key="input"
              explanation={explanation}
              setExplanation={setExplanation}
              charCount={charCount}
              wordCount={wordCount}
              minChars={minChars}
              maxChars={maxChars}
              isValidLength={isValidLength}
              canSubmit={canSubmit}
              remainingAttempts={remainingAttempts}
              analyzeError={analyzeError}
              onSubmit={handleSubmit}
              onClose={onClose}
            />
          )}

          {view === 'loading' && <LoadingView key="loading" />}

          {view === 'results' && analysis && (
            <ResultsView
              key="results"
              analysis={analysis}
              canRetry={canRetry}
              remainingAttempts={remainingAttempts}
              onContinue={handleContinue}
              onRetry={handleRetry}
              onSeekToTimestamp={handleSeekAndClose}
            />
          )}
        </AnimatePresence>
      </DialogContent>
    </Dialog>
  );
}

// Input View Component
function InputView({
  explanation,
  setExplanation,
  charCount,
  wordCount,
  minChars,
  maxChars,
  canSubmit,
  remainingAttempts,
  analyzeError,
  onSubmit,
  onClose,
}: {
  explanation: string;
  setExplanation: (text: string) => void;
  charCount: number;
  wordCount: number;
  minChars: number;
  maxChars: number;
  isValidLength: boolean;
  canSubmit: boolean;
  remainingAttempts: number;
  analyzeError: Error | null;
  onSubmit: () => void;
  onClose: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="p-8"
    >
      {/* Header */}
      <div className="text-center mb-6">
        {/* NEXO Icon */}
        <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/30 to-[var(--faiston-blue-mid,#2226C0)]/30 flex items-center justify-center">
          <Sparkles className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
        </div>

        <h2 className="text-2xl font-bold text-white flex items-center justify-center gap-2">
          <MessageCircle className="w-6 h-6 text-[var(--faiston-magenta-mid,#C31B8C)]" />
          Explique para o NEXO
        </h2>
        <p className="text-white/70 mt-2">
          O que voce entendeu sobre <span className="font-semibold text-white">esta aula</span>?
        </p>
        <p className="text-white/50 text-sm mt-1">(Minimo {minChars} caracteres)</p>
      </div>

      {/* Textarea */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-white/80">Sua explicacao</label>
        <Textarea
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          placeholder="Escreva como se fosse explicar para um amigo que nunca viu esse tema..."
          className="min-h-[180px] bg-white/5 border-white/10 text-white placeholder:text-white/30 resize-none rounded-xl focus:border-[var(--faiston-magenta-mid,#C31B8C)]/50"
          maxLength={maxChars}
        />

        {/* Character Counter */}
        <div className="flex justify-between items-center text-sm">
          <span
            className={
              charCount < minChars
                ? 'text-[var(--faiston-magenta-mid,#C31B8C)]'
                : 'text-[var(--faiston-magenta-mid,#C31B8C)]'
            }
          >
            {charCount} / {maxChars}
          </span>
          <span className="text-white/50">
            {wordCount} palavra{wordCount !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Error Message */}
      {analyzeError && (
        <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          Erro ao analisar. Tente novamente.
        </div>
      )}

      {/* Remaining Attempts */}
      {remainingAttempts < 3 && (
        <p className="text-center text-white/50 text-sm mt-4">
          {remainingAttempts} tentativa{remainingAttempts !== 1 ? 's' : ''} restante
          {remainingAttempts !== 1 ? 's' : ''}
        </p>
      )}

      {/* Buttons */}
      <div className="flex gap-3 mt-6">
        <Button
          variant="outline"
          onClick={onClose}
          className="flex-1 bg-white/5 border-white/20 text-white hover:bg-white/10 rounded-xl h-12"
        >
          Fechar
        </Button>
        <Button
          onClick={onSubmit}
          disabled={!canSubmit}
          className="flex-1 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white border-0 rounded-xl h-12 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Enviar Reflexao
        </Button>
      </div>
    </motion.div>
  );
}

// Loading View Component
function LoadingView() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="p-8 flex flex-col items-center justify-center min-h-[400px]"
    >
      {/* Spinner */}
      <div className="relative w-20 h-20 mb-6">
        <motion.div className="absolute inset-0 rounded-full border-4 border-white/10" />
        <motion.div
          className="absolute inset-0 rounded-full border-4 border-[var(--faiston-magenta-mid,#C31B8C)] border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      <h3 className="text-xl font-semibold text-white mb-2">NEXO esta analisando...</h3>
      <p className="text-white/60 text-center max-w-xs">
        Aguarde enquanto processamos sua reflexao.
        <br />
        Isso pode levar alguns segundos.
      </p>

      {/* Animated dots */}
      <div className="flex gap-2 mt-6">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-3 h-3 rounded-full bg-[var(--faiston-magenta-mid,#C31B8C)]"
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 1,
              repeat: Infinity,
              delay: i * 0.2,
            }}
          />
        ))}
      </div>
    </motion.div>
  );
}

// Timestamp Button Component
function TimestampButton({ timestamp, onSeek }: { timestamp: number; onSeek: (time: number) => void }) {
  return (
    <motion.button
      onClick={() => onSeek(timestamp)}
      className="mt-2 ml-4 flex items-center gap-2 px-4 py-2
                 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)]/10 to-[var(--faiston-blue-mid,#2226C0)]/10
                 border border-[var(--faiston-magenta-mid,#C31B8C)]/30 rounded-lg
                 hover:from-[var(--faiston-magenta-mid,#C31B8C)]/20 hover:shadow-[0_0_20px_rgba(195,27,140,0.3)]
                 transition-all duration-200"
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      aria-label={`Ir para o minuto ${formatTimestamp(timestamp)} do video`}
    >
      <Play className="w-4 h-4 text-[var(--faiston-magenta-mid,#C31B8C)]" />
      <span className="text-[var(--faiston-magenta-mid,#C31B8C)] text-sm">
        Ver aos {formatTimestamp(timestamp)}
      </span>
    </motion.button>
  );
}

// Results View Component
function ResultsView({
  analysis,
  canRetry,
  remainingAttempts,
  onContinue,
  onRetry,
  onSeekToTimestamp,
}: {
  analysis: {
    overall_score: number;
    coerencia: number;
    completude: number;
    precisao: number;
    pontos_fortes: string[];
    pontos_atencao: string[];
    proximos_passos: ProximoPasso[];
    xp_earned: number;
  };
  canRetry: boolean;
  remainingAttempts: number;
  onContinue: () => void;
  onRetry: () => void;
  onSeekToTimestamp: (time: number) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="max-h-[80vh] overflow-hidden"
    >
      <ScrollArea className="h-full max-h-[80vh]">
        <div className="p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', delay: 0.2 }}
              className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-green-500/30 to-green-600/30 flex items-center justify-center"
            >
              <CheckCircle2 className="w-8 h-8 text-green-400" />
            </motion.div>

            <h2 className="text-2xl font-bold text-white">Reflexao Concluida!</h2>
            <p className="text-white/60 mt-1">Veja o feedback sobre sua compreensao</p>
          </div>

          {/* Overall Score */}
          <div
            className={`p-6 rounded-2xl bg-gradient-to-br border mb-6 ${getScoreBgClass(analysis.overall_score)}`}
          >
            <div className="text-center">
              <p className="text-white/60 text-sm mb-1">Pontuacao Geral</p>
              <motion.p
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: 'spring', delay: 0.3 }}
                className={`text-5xl font-bold ${getScoreColorClass(analysis.overall_score)}`}
              >
                {analysis.overall_score}%
              </motion.p>

              {/* Sub-scores */}
              <div className="flex justify-center gap-6 mt-4 text-sm">
                <span className="text-white/60">
                  Coerencia:{' '}
                  <span className={getScoreColorClass(analysis.coerencia)}>{analysis.coerencia}%</span>
                </span>
                <span className="text-white/60">
                  Completude:{' '}
                  <span className={getScoreColorClass(analysis.completude)}>{analysis.completude}%</span>
                </span>
                <span className="text-white/60">
                  Precisao:{' '}
                  <span className={getScoreColorClass(analysis.precisao)}>{analysis.precisao}%</span>
                </span>
              </div>
            </div>
          </div>

          {/* Pontos Fortes */}
          {analysis.pontos_fortes.length > 0 && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 }}
              className="p-4 rounded-2xl bg-gradient-to-r from-green-500/10 to-green-600/5 border border-green-500/20 mb-4"
            >
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
                <h4 className="font-semibold text-green-400">Pontos Fortes</h4>
              </div>
              <ul className="space-y-2">
                {analysis.pontos_fortes.map((ponto, i) => (
                  <li key={i} className="text-white/80 text-sm flex items-start gap-2">
                    <span className="text-green-400 mt-1">•</span>
                    {ponto}
                  </li>
                ))}
              </ul>
            </motion.div>
          )}

          {/* Pontos de Atencao */}
          {analysis.pontos_atencao.length > 0 && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 }}
              className="p-4 rounded-2xl bg-gradient-to-r from-yellow-500/10 to-orange-500/5 border border-yellow-500/20 mb-4"
            >
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                <h4 className="font-semibold text-yellow-400">Pontos de Atencao</h4>
              </div>
              <ul className="space-y-2">
                {analysis.pontos_atencao.map((ponto, i) => (
                  <li key={i} className="text-white/80 text-sm flex items-start gap-2">
                    <span className="text-yellow-400 mt-1">•</span>
                    {ponto}
                  </li>
                ))}
              </ul>
            </motion.div>
          )}

          {/* Proximos Passos */}
          {analysis.proximos_passos.length > 0 && (
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.6 }}
              className="p-4 rounded-2xl bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)]/10 to-[var(--faiston-blue-mid,#2226C0)]/10 border border-[var(--faiston-magenta-mid,#C31B8C)]/20 mb-6"
            >
              <div className="flex items-center gap-2 mb-3">
                <Lightbulb className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
                <h4 className="font-semibold text-[var(--faiston-magenta-mid,#C31B8C)]">
                  Proximos Passos
                </h4>
              </div>
              <div className="space-y-4">
                {analysis.proximos_passos.map((passo, i) => (
                  <div key={i}>
                    <p className="text-white/80 text-sm flex items-start gap-2">
                      <span className="text-[var(--faiston-magenta-mid,#C31B8C)] mt-1">•</span>
                      <span>{passo.text}</span>
                    </p>
                    {passo.timestamp !== null && passo.timestamp !== undefined && (
                      <TimestampButton timestamp={passo.timestamp} onSeek={onSeekToTimestamp} />
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* XP Earned */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
            className="text-center mb-6"
          >
            <p className="text-white/60 text-sm">XP ganho nesta reflexao</p>
            <p className="text-2xl font-bold text-[var(--faiston-magenta-mid,#C31B8C)]">
              +{analysis.xp_earned} XP
            </p>
          </motion.div>

          {/* Buttons */}
          <div className="flex gap-3">
            <Button
              onClick={onContinue}
              className="flex-1 bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:opacity-90 text-white border-0 rounded-xl h-12"
            >
              Continuar Aprendendo
            </Button>
            {canRetry && (
              <Button
                variant="outline"
                onClick={onRetry}
                className="flex-1 bg-white/5 border-white/20 text-white hover:bg-white/10 rounded-xl h-12"
              >
                Nova Reflexao ({remainingAttempts})
              </Button>
            )}
          </div>
        </div>
      </ScrollArea>
    </motion.div>
  );
}
