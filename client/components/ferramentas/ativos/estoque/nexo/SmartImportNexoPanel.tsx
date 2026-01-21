'use client';

// =============================================================================
// SmartImportNexoPanel - NEXO Intelligent Import UI
// =============================================================================
// Inline UI component for the NEXO-guided import flow.
// Shows NEXO's analysis, reasoning trace, and clarification questions.
//
// Philosophy: NEXO guides user through import with intelligent analysis
// This component makes NEXO's thinking visible and interactive.
// =============================================================================

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Eye,
  MessageCircleQuestion,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Columns3,
  Lightbulb,
  Play,
  Loader2,
  Info,
  History,
  Sparkles,
  TrendingUp,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { DebugAnalysisPanel } from '@/components/shared/DebugAnalysisPanel';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import {
  useSmartImportNexo,
  type NexoReasoningStep,
  type NexoQuestion,
  type NexoSheetAnalysis,
  type NexoColumnMapping,
  type NexoMissingColumn,
} from '@/hooks/ativos/useSmartImportNexo';
import { NexoExplanation } from '@/components/shared/nexo-explanation';
import {
  REASONING_TRACE_EXPLANATION,
  QUESTIONS_CRITICAL_EXPLANATION,
  QUESTIONS_OPTIONAL_EXPLANATION,
  FREE_TEXT_EXPLANATION,
  REVIEW_SUMMARY_EXPLANATION,
  ERROR_EXPLANATION,
  SUCCESS_EXPLANATION,
  LOADING_EXPLANATIONS,
  getColumnMappingsExplanation,
  getSheetAnalysisExplanation,
  getPriorKnowledgeExplanation,
  getFileInfoExplanation,
} from '@/lib/ativos/nexoImportExplanations';

// =============================================================================
// Types
// =============================================================================

interface SmartImportNexoPanelProps {
  file: File | null;
  onComplete: (sessionId: string) => void;
  onCancel: () => void;
}

// =============================================================================
// Sub-Components
// =============================================================================

/**
 * Displays NEXO's reasoning trace (thoughts, actions, observations).
 */
function ReasoningTrace({ steps }: { steps: NexoReasoningStep[] }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (steps.length === 0) return null;

  // Show only last 3 steps when collapsed
  const visibleSteps = isExpanded ? steps : steps.slice(-3);

  const getIcon = (type: NexoReasoningStep['type']) => {
    switch (type) {
      case 'thought':
        return <Brain className="w-4 h-4 text-purple-400" />;
      case 'action':
        return <Play className="w-4 h-4 text-cyan-400" />;
      case 'observation':
        return <Eye className="w-4 h-4 text-green-400" />;
    }
  };

  const getLabel = (type: NexoReasoningStep['type']) => {
    switch (type) {
      case 'thought':
        return 'Pensando';
      case 'action':
        return 'Ação';
      case 'observation':
        return 'Observação';
    }
  };

  return (
    <div className="space-y-2">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm text-text-muted hover:text-text-primary transition-colors"
      >
        <Lightbulb className="w-4 h-4" />
        <span>Como NEXO está pensando</span>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4" />
        ) : (
          <ChevronDown className="w-4 h-4" />
        )}
        <Badge variant="outline" className="ml-auto">
          {steps.length} passos
        </Badge>
      </button>

      <AnimatePresence>
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="space-y-2 pl-2 border-l-2 border-white/10"
        >
          {/* NEXO Explanation for reasoning trace */}
          <NexoExplanation
            summary={REASONING_TRACE_EXPLANATION.summary}
            details={REASONING_TRACE_EXPLANATION.details}
            action={REASONING_TRACE_EXPLANATION.action}
            variant="info"
            compact
          />

          {visibleSteps.map((step, index) => (
            <motion.div
              key={index}
              initial={{ x: -10, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: index * 0.1 }}
              className="flex items-start gap-2 text-sm"
            >
              {getIcon(step.type)}
              <div>
                <span className="text-text-muted text-xs">
                  {getLabel(step.type)}:
                </span>
                <p className="text-text-secondary">{step.content}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/**
 * Displays sheet analysis with purpose detection.
 * Handles both backend field name variations:
 * - Frontend expects: purpose, confidence
 * - Backend may send: detected_purpose, purpose_confidence
 */
function SheetAnalysis({ sheets }: { sheets: NexoSheetAnalysis[] }) {
  const getPurposeLabel = (purpose: NexoSheetAnalysis['purpose'] | undefined) => {
    const labels: Record<NexoSheetAnalysis['purpose'], string> = {
      items: 'Itens',
      serials: 'Seriais',
      metadata: 'Metadados',
      summary: 'Resumo',
      config: 'Configuração',
      unknown: 'Desconhecido',
    };
    return labels[purpose ?? 'unknown'] ?? 'Desconhecido';
  };

  const getPurposeColor = (purpose: NexoSheetAnalysis['purpose'] | undefined) => {
    const colors: Record<NexoSheetAnalysis['purpose'], string> = {
      items: 'bg-cyan-500/20 text-cyan-400',
      serials: 'bg-purple-500/20 text-purple-400',
      metadata: 'bg-yellow-500/20 text-yellow-400',
      summary: 'bg-green-500/20 text-green-400',
      config: 'bg-blue-500/20 text-blue-400',
      unknown: 'bg-gray-500/20 text-gray-400',
    };
    return colors[purpose ?? 'unknown'] ?? 'bg-gray-500/20 text-gray-400';
  };

  // Helper to get purpose from either field name
  const getSheetPurpose = (sheet: NexoSheetAnalysis): NexoSheetAnalysis['purpose'] => {
    // Try standard field first, fallback to backend's detected_purpose
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return sheet.purpose ?? (sheet as any).detected_purpose ?? 'unknown';
  };

  // Helper to get confidence from either field name
  const getSheetConfidence = (sheet: NexoSheetAnalysis): number => {
    // Try standard field first, fallback to backend's purpose_confidence
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const confidence = sheet.confidence ?? (sheet as any).purpose_confidence ?? 0;
    // Guard against NaN
    return isNaN(confidence) ? 0 : confidence;
  };

  // Get dynamic explanation based on sheet count
  const sheetExplanation = getSheetAnalysisExplanation(sheets.length);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm text-text-muted">
        <FileSpreadsheet className="w-4 h-4" />
        <span>Abas detectadas</span>
        <Badge variant="outline">{sheets.length}</Badge>
      </div>

      {/* NEXO Explanation for sheet analysis */}
      <NexoExplanation
        summary={sheetExplanation.summary}
        details={sheetExplanation.details}
        action={sheetExplanation.action}
        variant="tip"
        compact
      />

      <div className="grid gap-2">
        {sheets.map((sheet, index) => {
          const purpose = getSheetPurpose(sheet);
          const confidence = getSheetConfidence(sheet);

          return (
            <div
              key={index}
              className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/10"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded bg-white/10 flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </div>
                <div>
                  <p className="text-sm font-medium">{sheet.name}</p>
                  <p className="text-xs text-text-muted">
                    {sheet.row_count.toLocaleString()} linhas · {sheet.column_count} colunas
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Badge className={getPurposeColor(purpose)}>
                  {getPurposeLabel(purpose)}
                </Badge>
                <Badge variant="outline">
                  {Math.round(confidence * 100)}%
                </Badge>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Displays column mappings with confidence.
 */
function ColumnMappings({ mappings }: { mappings: NexoColumnMapping[] }) {
  const [showAll, setShowAll] = useState(false);

  // Group by confidence level
  const highConfidence = mappings.filter(m => m.confidence >= 0.8);
  const mediumConfidence = mappings.filter(m => m.confidence >= 0.5 && m.confidence < 0.8);
  const lowConfidence = mappings.filter(m => m.confidence < 0.5);

  const visibleMappings = showAll ? mappings : mappings.slice(0, 5);

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-400';
    if (confidence >= 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  // Get dynamic explanation based on confidence counts
  const mappingExplanation = getColumnMappingsExplanation(
    highConfidence.length,
    mediumConfidence.length,
    lowConfidence.length
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Columns3 className="w-4 h-4" />
          <span>Mapeamento de colunas</span>
        </div>
        <div className="flex gap-2">
          <Badge className="bg-green-500/20 text-green-400">
            {highConfidence.length} alta
          </Badge>
          <Badge className="bg-yellow-500/20 text-yellow-400">
            {mediumConfidence.length} média
          </Badge>
          <Badge className="bg-red-500/20 text-red-400">
            {lowConfidence.length} baixa
          </Badge>
        </div>
      </div>

      {/* NEXO Explanation for column mappings - PRIORITY section */}
      <NexoExplanation
        summary={mappingExplanation.summary}
        details={mappingExplanation.details}
        action={mappingExplanation.action}
        variant="tip"
        compact
      />

      <div className="space-y-1">
        {visibleMappings.map((mapping, index) => (
          <div
            key={index}
            className="flex items-center justify-between p-2 bg-white/5 rounded text-sm"
          >
            <div className="flex items-center gap-2">
              <span className="text-text-muted">{mapping.file_column}</span>
              <span className="text-text-muted">→</span>
              <span className="font-medium">{mapping.target_field}</span>
            </div>
            <span className={getConfidenceColor(mapping.confidence)}>
              {Math.round(mapping.confidence * 100)}%
            </span>
          </div>
        ))}
      </div>

      {mappings.length > 5 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="text-sm text-cyan-400 hover:underline"
        >
          {showAll ? 'Mostrar menos' : `Ver todas ${mappings.length} colunas`}
        </button>
      )}
    </div>
  );
}

/**
 * Interactive question panel for user input.
 */
function QuestionPanel({
  questions,
  answers,
  onAnswer,
  onSubmit,
  onSkip,
  isSubmitting,
}: {
  questions: NexoQuestion[];
  answers: Record<string, string>;
  onAnswer: (questionId: string, answer: string) => void;
  onSubmit: (freeText: string, correctedAnswers: Record<string, string>) => void;
  onSkip: () => void;
  isSubmitting: boolean;
}) {
  // State for "Outros" text input per question
  const [otherTexts, setOtherTexts] = useState<Record<string, string>>({});
  // State for free text feedback field
  const [freeText, setFreeText] = useState('');

  // Separate unmapped questions (AGI-like) from regular questions
  const unmappedQuestions = questions.filter(q => q.topic === 'unmapped');
  const regularQuestions = questions.filter(q => q.topic !== 'unmapped');

  const criticalQuestions = regularQuestions.filter(q => q.importance === 'critical');
  const optionalQuestions = regularQuestions.filter(q => q.importance !== 'critical');

  // Check if critical questions are answered (including "Outros" with text)
  const allCriticalAnswered = criticalQuestions.every(q => {
    const answer = answers[q.id];
    if (answer === '__other__') {
      // "Outros" requires text to be filled
      return otherTexts[q.id]?.trim().length > 0;
    }
    return !!answer;
  });

  // Check if all unmapped (blocking) questions are answered
  // These questions don't have "Outros" option, just the 3 fixed options
  const allUnmappedAnswered = unmappedQuestions.every(q => !!answers[q.id]);

  // Both critical regular questions AND unmapped questions must be answered
  const canSubmit = allCriticalAnswered && allUnmappedAnswered;

  // Handler for "Outros" text changes
  const handleOtherTextChange = (questionId: string, text: string) => {
    setOtherTexts(prev => ({ ...prev, [questionId]: text }));
  };

  // Build corrected answers SYNCHRONOUSLY (fixes React async state race condition)
  // FIX: "__other__" was being sent to backend because onAnswer() state updates are async
  // Solution: Build the corrected answers object without relying on React state updates
  const handleSubmit = () => {
    // Build corrected answers synchronously - do NOT rely on React state updates
    const correctedAnswers: Record<string, string> = {};

    Object.keys(answers).forEach(questionId => {
      const answer = answers[questionId];
      if (answer === '__other__') {
        // Replace "__other__" with actual text if provided
        const otherText = otherTexts[questionId]?.trim();
        if (otherText) {
          correctedAnswers[questionId] = `Outros: ${otherText}`;
        }
        // If no text provided, omit this answer (don't send "__other__" to backend)
      } else {
        // Keep non-"__other__" answers as-is
        correctedAnswers[questionId] = answer;
      }
    });

    // Pass corrected answers directly to avoid React async state race condition
    onSubmit(freeText.trim(), correctedAnswers);
  };

  const getImportanceBadge = (importance: NexoQuestion['importance']) => {
    const styles: Record<NexoQuestion['importance'], string> = {
      critical: 'bg-red-500/20 text-red-400',
      high: 'bg-orange-500/20 text-orange-400',
      medium: 'bg-yellow-500/20 text-yellow-400',
      low: 'bg-gray-500/20 text-gray-400',
    };
    const labels: Record<NexoQuestion['importance'], string> = {
      critical: 'Obrigatório',
      high: 'Importante',
      medium: 'Opcional',
      low: 'Opcional',
    };
    return (
      <Badge className={styles[importance]}>{labels[importance]}</Badge>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <MessageCircleQuestion className="w-5 h-5 text-purple-400" />
        <h3 className="font-medium">NEXO precisa da sua ajuda</h3>
        <Badge variant="outline">{questions.length} perguntas</Badge>
      </div>

      {/* Unmapped columns first (AGI-like - blocking questions) */}
      {unmappedQuestions.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 p-3 bg-orange-500/10 rounded-lg border border-orange-500/20">
            <AlertTriangle className="w-5 h-5 text-orange-400" />
            <div>
              <p className="text-sm font-medium text-orange-300">
                {unmappedQuestions.length} coluna(s) não existe(m) no banco de dados
              </p>
              <p className="text-xs text-orange-200/70">
                Escolha o que fazer com cada coluna antes de continuar
              </p>
            </div>
          </div>

          {unmappedQuestions.map((question) => (
            <UnmappedColumnQuestionItem
              key={question.id}
              question={question}
              answer={answers[question.id]}
              onAnswer={onAnswer}
            />
          ))}
        </div>
      )}

      {/* Critical questions */}
      {criticalQuestions.length > 0 && (
        <div className="space-y-4">
          <p className="text-sm text-text-muted flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            Estas respostas são necessárias para continuar:
          </p>

          {/* NEXO Explanation for critical questions */}
          <NexoExplanation
            summary={QUESTIONS_CRITICAL_EXPLANATION.summary}
            details={QUESTIONS_CRITICAL_EXPLANATION.details}
            action={QUESTIONS_CRITICAL_EXPLANATION.action}
            variant="warning"
            compact
          />

          {criticalQuestions.map((question) => (
            <QuestionItem
              key={question.id}
              question={question}
              answer={answers[question.id]}
              otherText={otherTexts[question.id]}
              onAnswer={onAnswer}
              onOtherTextChange={handleOtherTextChange}
              importanceBadge={getImportanceBadge(question.importance)}
            />
          ))}
        </div>
      )}

      {/* Optional questions */}
      {optionalQuestions.length > 0 && (
        <div className="space-y-4 pt-4 border-t border-white/10">
          <p className="text-sm text-text-muted">
            Perguntas opcionais (respostas padrão serão usadas se não responder):
          </p>

          {/* NEXO Explanation for optional questions */}
          <NexoExplanation
            summary={QUESTIONS_OPTIONAL_EXPLANATION.summary}
            details={QUESTIONS_OPTIONAL_EXPLANATION.details}
            action={QUESTIONS_OPTIONAL_EXPLANATION.action}
            variant="info"
            compact
          />

          {optionalQuestions.map((question) => (
            <QuestionItem
              key={question.id}
              question={question}
              answer={answers[question.id]}
              otherText={otherTexts[question.id]}
              onAnswer={onAnswer}
              onOtherTextChange={handleOtherTextChange}
              importanceBadge={getImportanceBadge(question.importance)}
            />
          ))}
        </div>
      )}

      {/* Free text feedback field */}
      <div className="space-y-3 pt-4 border-t border-white/10">
        <NexoExplanation
          summary={FREE_TEXT_EXPLANATION.summary}
          details={FREE_TEXT_EXPLANATION.details}
          action={FREE_TEXT_EXPLANATION.action}
          variant="tip"
          compact
        />
        <textarea
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="Ex: A coluna 'EQUIP' na verdade é o Part Number, não o nome do equipamento..."
          className="w-full p-3 bg-white/5 border border-white/10 rounded-lg text-sm text-text-primary placeholder:text-text-muted/50 focus:outline-none focus:ring-2 focus:ring-faiston-magenta-light/50 focus:border-transparent resize-none"
          rows={3}
        />
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3 pt-4">
        <Button
          variant="outline"
          onClick={onSkip}
          disabled={isSubmitting}
        >
          Pular e usar padrões
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
          className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Processando...
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Confirmar respostas
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

/**
 * Normalize option to always have value and label.
 * Handles cases where Gemini returns strings instead of objects.
 */
function normalizeOption(
  option: string | { value?: string; label?: string; description?: string },
  index: number
): { value: string; label: string; description?: string } {
  // If option is a string, convert to object
  if (typeof option === 'string') {
    return {
      value: option.toLowerCase().replace(/\s+/g, '_'),
      label: option,
    };
  }

  // If option is object but missing value/label, add fallbacks
  const value = option.value || option.label || `option_${index}`;
  const label = option.label || option.value || `Opção ${index + 1}`;

  return {
    value,
    label,
    description: option.description,
  };
}

/**
 * Single question item with radio options and "Outros" textarea.
 */
function QuestionItem({
  question,
  answer,
  otherText,
  onAnswer,
  onOtherTextChange,
  importanceBadge,
}: {
  question: NexoQuestion;
  answer?: string;
  otherText?: string;
  onAnswer: (questionId: string, answer: string) => void;
  onOtherTextChange?: (questionId: string, text: string) => void;
  importanceBadge: React.ReactNode;
}) {
  // Normalize all options to ensure they have value/label
  const normalizedOptions = (question.options || []).map((opt, idx) =>
    normalizeOption(opt as string | { value?: string; label?: string; description?: string }, idx)
  );

  // Check if "Outros" is selected
  const isOtherSelected = answer === '__other__';

  return (
    <div className="p-4 bg-white/5 rounded-lg border border-white/10 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium">{question.question}</p>
          {question.context && (
            <p className="text-sm text-text-muted mt-1 flex items-start gap-2">
              <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
              {question.context}
            </p>
          )}
        </div>
        {importanceBadge}
      </div>

      <RadioGroup
        value={answer ?? ''}
        onValueChange={(value: string) => onAnswer(question.id, value)}
        className="space-y-2"
      >
        {/* Render normalized options */}
        {normalizedOptions.map((option) => (
          <div key={option.value} className="flex items-start space-x-3">
            <RadioGroupItem
              value={option.value}
              id={`${question.id}-${option.value}`}
              className="mt-1"
            />
            <Label
              htmlFor={`${question.id}-${option.value}`}
              className="flex-1 cursor-pointer"
            >
              <span className="font-medium">{option.label}</span>
              {option.description && (
                <p className="text-sm text-text-muted">{option.description}</p>
              )}
            </Label>
          </div>
        ))}

        {/* "Outros" option - always present */}
        <div className="flex items-start space-x-3">
          <RadioGroupItem
            value="__other__"
            id={`${question.id}-__other__`}
            className="mt-1"
          />
          <Label
            htmlFor={`${question.id}-__other__`}
            className="flex-1 cursor-pointer"
          >
            <span className="font-medium">Outros</span>
            <p className="text-sm text-text-muted">Especificar uma resposta diferente</p>
          </Label>
        </div>
      </RadioGroup>

      {/* Textarea for "Outros" - appears when selected */}
      {isOtherSelected && (
        <div className="mt-3 pl-7">
          <textarea
            value={otherText || ''}
            onChange={(e) => onOtherTextChange?.(question.id, e.target.value)}
            placeholder="Descreva sua resposta..."
            className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg text-sm
                       placeholder:text-text-muted focus:outline-none focus:ring-2
                       focus:ring-purple-500/50 focus:border-purple-500/50 resize-none"
            rows={3}
          />
        </div>
      )}
    </div>
  );
}

/**
 * Unmapped Column Question Item - AGI-like UI for columns not in DB schema.
 * Shows 3 options with visual indicators:
 * - Ignore (warning) - Data will be lost
 * - Store in metadata (recommended) - Preserve in JSONB field
 * - Request DB update (contact_it) - Instruct user to contact IT
 */
function UnmappedColumnQuestionItem({
  question,
  answer,
  onAnswer,
}: {
  question: NexoQuestion;
  answer?: string;
  onAnswer: (questionId: string, answer: string) => void;
}) {
  // Check if "request_db_update" is selected to show IT contact info
  const showItContactNote = answer === 'request_db_update' && question.it_contact_note;

  return (
    <div className="p-4 bg-orange-500/5 rounded-lg border border-orange-500/20 space-y-4">
      {/* Header with column name and blocking badge */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            <Badge className="bg-orange-500/20 text-orange-400 text-xs">
              Coluna não mapeada
            </Badge>
            {question.blocking && (
              <Badge className="bg-red-500/20 text-red-400 text-xs">
                Bloqueante
              </Badge>
            )}
          </div>
          <p className="font-medium text-orange-200">{question.question}</p>
          {question.context && (
            <p className="text-sm text-text-muted mt-1">
              {question.context}
            </p>
          )}
        </div>
      </div>

      {/* Options with visual indicators */}
      <RadioGroup
        value={answer ?? ''}
        onValueChange={(value: string) => onAnswer(question.id, value)}
        className="space-y-3"
      >
        {question.options.map((option) => {
          const isWarning = option.warning;
          const isRecommended = option.recommended;
          const isContactIt = option.contact_it;

          // Different background styles based on option type
          const optionBgClass = isWarning
            ? 'bg-red-500/10 border-red-500/20 hover:bg-red-500/15'
            : isRecommended
            ? 'bg-green-500/10 border-green-500/20 hover:bg-green-500/15'
            : isContactIt
            ? 'bg-blue-500/10 border-blue-500/20 hover:bg-blue-500/15'
            : 'bg-white/5 border-white/10 hover:bg-white/10';

          return (
            <div
              key={option.value}
              className={`p-3 rounded-lg border transition-colors ${optionBgClass}`}
            >
              <div className="flex items-start space-x-3">
                <RadioGroupItem
                  value={option.value}
                  id={`${question.id}-${option.value}`}
                  className="mt-1"
                />
                <Label
                  htmlFor={`${question.id}-${option.value}`}
                  className="flex-1 cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{option.label}</span>
                    {isWarning && (
                      <Badge className="bg-red-500/30 text-red-300 text-xs">
                        ⚠️ Dados perdidos
                      </Badge>
                    )}
                    {isRecommended && (
                      <Badge className="bg-green-500/30 text-green-300 text-xs">
                        ✓ Recomendado
                      </Badge>
                    )}
                    {isContactIt && (
                      <Badge className="bg-blue-500/30 text-blue-300 text-xs">
                        📧 Contatar TI
                      </Badge>
                    )}
                  </div>
                  {option.description && (
                    <p className="text-sm text-text-muted mt-1">{option.description}</p>
                  )}
                </Label>
              </div>
            </div>
          );
        })}
      </RadioGroup>

      {/* IT Contact Note - shown when "request_db_update" is selected */}
      {showItContactNote && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20"
        >
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-blue-200">{question.it_contact_note}</p>
          </div>
        </motion.div>
      )}
    </div>
  );
}

/**
 * Missing Columns Alert - Blocking UI when columns don't exist in PostgreSQL.
 * FIX (January 2026): Instead of trying to create columns automatically,
 * we block the import and inform user to contact IT.
 */
function MissingColumnsAlert({
  columns,
  message,
  onCancel,
}: {
  columns: NexoMissingColumn[];
  message: string;
  onCancel: () => void;
}) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <XCircle className="w-6 h-6 text-red-400" />
        <h3 className="text-lg font-semibold text-red-300">
          Importação Bloqueada - Campos Faltantes
        </h3>
      </div>

      {/* Blocking alert card */}
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 space-y-4">
        <p className="text-white/70">
          Os seguintes campos não existem no banco de dados:
        </p>

        {/* Missing columns list */}
        <ul className="space-y-2 font-mono text-sm">
          {columns.map((col) => (
            <li key={col.name} className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300">
                {col.type}
              </span>
              <span className="text-white">{col.name}</span>
              <span className="text-white/40">← &ldquo;{col.source}&rdquo;</span>
            </li>
          ))}
        </ul>

        {/* Instructions for user */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4 space-y-2">
          <p className="text-blue-200 text-sm">
            <strong>Ação necessária:</strong> Contacte a equipe de tecnologia para
            criar estes campos na tabela <code className="bg-blue-500/20 px-1 rounded">sga.pending_entry_items</code>.
          </p>
          <p className="text-blue-200/70 text-sm">
            Após a criação dos campos, faça upload do arquivo novamente para uma nova análise.
          </p>
        </div>
      </div>

      {/* Cancel button - only option when blocked */}
      <div className="flex justify-end pt-4 border-t border-white/10">
        <Button
          variant="outline"
          onClick={onCancel}
          className="border-red-500/30 text-red-300 hover:bg-red-500/10"
        >
          <XCircle className="w-4 h-4 mr-2" />
          Cancelar Importação
        </Button>
      </div>
    </div>
  );
}

/**
 * Import Review Panel - HIL approval step before final import.
 * Shows summary of what NEXO understood and asks for user confirmation.
 */
function ImportReviewPanel({
  reviewSummary,
  userFeedback,
  onApprove,
  onBack,
  onCancel,
  isSubmitting,
}: {
  reviewSummary: import('@/hooks/ativos/useSmartImportNexo').NexoReviewSummary;
  userFeedback: string | null;
  onApprove: () => void;
  onBack: () => void;
  onCancel: () => void;
  isSubmitting: boolean;
}) {
  // FIX (January 2026): Show blocking alert when import is blocked due to missing columns
  if (reviewSummary.isBlocked && reviewSummary.missingColumns && reviewSummary.missingColumns.length > 0) {
    return (
      <MissingColumnsAlert
        columns={reviewSummary.missingColumns}
        message={reviewSummary.blockMessage || 'Campos faltantes no banco de dados.'}
        onCancel={onCancel}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-5 h-5 text-green-400" />
        <h3 className="font-medium">Resumo da Importação</h3>
      </div>

      {/* NEXO Explanation */}
      <NexoExplanation
        summary={REVIEW_SUMMARY_EXPLANATION.summary}
        details={REVIEW_SUMMARY_EXPLANATION.details}
        action={REVIEW_SUMMARY_EXPLANATION.action}
        variant="success"
      />

      {/* Summary card */}
      <div className="p-4 bg-white/5 rounded-lg border border-white/10 space-y-4">
        {/* File info */}
        <div className="flex items-center gap-3">
          <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
          <div>
            <p className="font-medium">{reviewSummary.filename}</p>
            <p className="text-sm text-text-muted">
              Aba principal: {reviewSummary.mainSheet}
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 pt-3 border-t border-white/10">
          <div>
            <p className="text-sm text-text-muted">Total de itens</p>
            <p className="text-xl font-bold text-cyan-400">
              {reviewSummary.totalItems.toLocaleString()}
            </p>
          </div>
          {reviewSummary.projectName && (
            <div>
              <p className="text-sm text-text-muted">Projeto</p>
              <p className="text-lg font-medium">{reviewSummary.projectName}</p>
            </div>
          )}
        </div>

        {/* Validations */}
        {reviewSummary.validations.length > 0 && (
          <div className="pt-3 border-t border-white/10">
            <p className="text-sm text-text-muted mb-2 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              Validações OK:
            </p>
            <ul className="space-y-1">
              {reviewSummary.validations.map((validation, i) => (
                <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                  <span className="text-green-400">✓</span>
                  {validation}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings */}
        {reviewSummary.warnings.length > 0 && (
          <div className="pt-3 border-t border-white/10">
            <p className="text-sm text-text-muted mb-2 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400" />
              Atenção:
            </p>
            <ul className="space-y-1">
              {reviewSummary.warnings.map((warning, i) => (
                <li key={i} className="text-sm text-yellow-400 flex items-start gap-2">
                  <span>⚠</span>
                  {warning}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* New columns to be created (Dynamic Schema Evolution) */}
        {reviewSummary.newColumns && reviewSummary.newColumns.length > 0 && (
          <div className="pt-3 border-t border-white/10">
            <p className="text-sm text-text-muted mb-2 flex items-center gap-2">
              <Columns3 className="w-4 h-4 text-purple-400" />
              Novos campos a criar no banco de dados:
            </p>
            <div className="space-y-2">
              {reviewSummary.newColumns.map((col, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 bg-purple-500/10 rounded border border-purple-500/20"
                >
                  <div className="flex items-center gap-2">
                    <Badge className="bg-purple-500/20 text-purple-400 text-xs">
                      {col.inferredType}
                    </Badge>
                    <span className="text-sm font-medium text-text-primary">
                      {col.name}
                    </span>
                  </div>
                  <span className="text-xs text-text-muted">
                    {col.sourceFileColumn && `de "${col.sourceFileColumn}"`}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs text-text-muted mt-2 italic">
              Estes campos serão criados automaticamente no schema do banco de dados.
            </p>
          </div>
        )}

        {/* User feedback if provided */}
        {userFeedback && (
          <div className="pt-3 border-t border-white/10">
            <p className="text-sm text-text-muted mb-2 flex items-center gap-2">
              <MessageCircleQuestion className="w-4 h-4 text-purple-400" />
              Seu feedback:
            </p>
            <p className="text-sm text-text-secondary italic">
              &ldquo;{userFeedback}&rdquo;
            </p>
          </div>
        )}
      </div>

      {/* NEXO recommendation */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="p-4 bg-gradient-to-r from-green-500/10 to-cyan-500/10 rounded-lg border border-green-500/20"
      >
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-green-400">Recomendação NEXO</p>
            <p className="text-sm text-text-secondary mt-1">
              {reviewSummary.recommendation}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Actions */}
      <div className="flex justify-between items-center pt-4 border-t border-white/10">
        <Button
          variant="ghost"
          onClick={onBack}
          disabled={isSubmitting}
          className="text-text-muted hover:text-text-primary"
        >
          <ChevronUp className="w-4 h-4 mr-2" />
          Voltar e editar respostas
        </Button>

        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancelar
          </Button>
          <Button
            onClick={onApprove}
            disabled={isSubmitting || !reviewSummary.readyToImport}
            className="bg-gradient-to-r from-green-500 to-cyan-500 text-white"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Importando...
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Aprovar e Importar
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function SmartImportNexoPanel({
  file,
  onComplete,
  onCancel,
}: SmartImportNexoPanelProps) {
  const {
    state,
    isAnalyzing,
    isRecalling,
    hasQuestions,
    isReadyToProcess,
    isReviewing,
    startAnalysis,
    answerQuestion,
    submitAllAnswers,
    skipQuestions,
    approveAndImport,
    backToQuestions,
    // Note: prepareProcessing removed - approveAndImport calls it internally
    reasoningTrace,
    currentThought,
    priorKnowledge,
    reviewSummary,
  } = useSmartImportNexo();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);

  // Rotating loading messages for better UX during ~30s Gemini processing
  const LOADING_MESSAGES = [
    { text: 'Analisando estrutura do arquivo...', emoji: '🔍' },
    { text: 'Identificando colunas e campos...', emoji: '📋' },
    { text: 'Consultando base de conhecimento...', emoji: '🧠' },
    { text: 'Processando com IA generativa...', emoji: '✨' },
    { text: 'Mapeando dados para o sistema...', emoji: '🗺️' },
    { text: 'Verificando padrões anteriores...', emoji: '📊' },
    { text: 'Preparando perguntas de validação...', emoji: '❓' },
    { text: 'Quase lá, finalizando análise...', emoji: '🎯' },
  ];

  // Rotate messages every 4 seconds during loading
  useEffect(() => {
    if (!isAnalyzing && !isRecalling) {
      setLoadingMessageIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingMessageIndex(prev => (prev + 1) % LOADING_MESSAGES.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [isAnalyzing, isRecalling, LOADING_MESSAGES.length]);

  // Start analysis when file changes (CRITICAL: useEffect for side effects, NOT useMemo)
  useEffect(() => {
    if (file && state.stage === 'idle') {
      startAnalysis(file).catch(err => {
        console.error('[NEXO] Analysis failed:', err);
      });
    }
  }, [file, state.stage, startAnalysis]);

  // Handle submit answers (with corrected answers to avoid "__other__" race condition)
  // FIX: Now receives pre-corrected answers that don't contain "__other__" values
  const handleSubmitAnswers = async (
    freeText: string = '',
    correctedAnswers?: Record<string, string>
  ) => {
    setIsSubmitting(true);
    try {
      await submitAllAnswers(freeText || undefined, correctedAnswers);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle approve and import (HIL approval)
  // FIX (January 2026): Previously this silently swallowed errors, causing UI loop
  // Now shows error message to user so they understand why import didn't proceed
  const handleApproveAndImport = async () => {
    setIsSubmitting(true);
    try {
      await approveAndImport();
      onComplete(state.analysis!.sessionId);
    } catch (err) {
      console.error('[NEXO] Import failed:', err);
      // FIX: Show error to user instead of silently failing
      const message = err instanceof Error ? err.message : 'Erro ao executar importação';
      alert(`Falha na importação: ${message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle back to questions (from review screen)
  const handleBackToQuestions = () => {
    backToQuestions();
  };

  // Handle skip questions
  const handleSkipQuestions = async () => {
    setIsSubmitting(true);
    try {
      await skipQuestions();
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle continue to processing
  // FIX (January 2026): Must call approveAndImport() to execute actual import,
  // not just prepareProcessing() which only validates configuration
  // FIX (January 2026): Handle case where reviewSummary is null - generate it first
  const handleContinue = async () => {
    setIsSubmitting(true);
    try {
      // If we don't have a reviewSummary, we need to go through the review stage first
      // This happens when the flow skipped the 'reviewing' stage unexpectedly
      if (!reviewSummary) {
        throw new Error('Sessão de revisão não encontrada. Por favor, responda às perguntas novamente.');
      }

      await approveAndImport();
      onComplete(state.analysis!.sessionId);
    } catch (err) {
      console.error('[NEXO] Import failed:', err);
      const message = err instanceof Error ? err.message : 'Erro ao executar importação';
      alert(message); // Temporary - should use proper toast/notification
    } finally {
      setIsSubmitting(false);
    }
  };

  // Loading state (uploading, recalling, analyzing, or re-analyzing) - COMBO COMPLETO
  const isReAnalyzing = state.stage === 're-analyzing';
  if (state.stage === 'uploading' || isRecalling || isAnalyzing || isReAnalyzing) {
    const stageInfo = {
      'uploading': { title: 'Enviando Arquivo', gradient: 'from-cyan-500 to-blue-500' },
      'recalling': { title: 'NEXO Consultando Memória', gradient: 'from-purple-500 to-pink-500' },
      'analyzing': { title: 'NEXO Analisando com IA', gradient: 'from-purple-500 to-pink-500' },
      're-analyzing': { title: 'NEXO Reavaliando Respostas', gradient: 'from-orange-500 to-red-500' },
    };
    const currentStageKey = state.stage as 'uploading' | 'recalling' | 'analyzing' | 're-analyzing';
    const { title, gradient } = stageInfo[currentStageKey] || stageInfo.analyzing;
    const currentMessage = LOADING_MESSAGES[loadingMessageIndex];

    return (
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className={`p-1.5 rounded-lg bg-gradient-to-br ${gradient}`}
            >
              <Brain className="w-5 h-5 text-white" />
            </motion.div>
            <GlassCardTitle>{title}</GlassCardTitle>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-6">
            {/* Main pulsing icon with file name */}
            <div className="flex flex-col items-center gap-4 py-4">
              <motion.div
                animate={{
                  scale: [1, 1.1, 1],
                  opacity: [0.7, 1, 0.7],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                className={`w-20 h-20 rounded-2xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-lg shadow-purple-500/25`}
              >
                <Brain className="w-10 h-10 text-white" />
              </motion.div>

              <div className="text-center">
                <p className="text-sm font-medium text-text-primary truncate max-w-[200px]">
                  {file?.name}
                </p>
                <p className="text-xs text-text-muted">
                  {file?.size ? `${(file.size / 1024).toFixed(1)} KB` : ''}
                </p>
              </div>
            </div>

            {/* Progress bar */}
            <div className="space-y-2">
              <Progress value={state.progress.percent} className="h-2" />
              <p className="text-xs text-text-muted text-center">
                {state.progress.percent}% concluído
              </p>
            </div>

            {/* Rotating messages with AnimatePresence */}
            <AnimatePresence mode="wait">
              <motion.div
                key={isReAnalyzing ? state.progress.message : loadingMessageIndex}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className={`flex items-center justify-center gap-2 p-3 rounded-lg border ${
                  isReAnalyzing
                    ? 'bg-orange-500/10 border-orange-500/20'
                    : 'bg-purple-500/10 border-purple-500/20'
                }`}
              >
                {isReAnalyzing ? (
                  <>
                    <span className="text-lg">🔄</span>
                    <p className="text-sm text-text-secondary">{state.progress.message}</p>
                  </>
                ) : (
                  <>
                    <span className="text-lg">{currentMessage.emoji}</span>
                    <p className="text-sm text-text-secondary">{currentMessage.text}</p>
                  </>
                )}
              </motion.div>
            </AnimatePresence>

            {/* Current thought from agent (if available) */}
            {currentThought && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-start gap-2 p-3 bg-cyan-500/10 rounded-lg border border-cyan-500/20"
              >
                <Lightbulb className="w-4 h-4 text-cyan-400 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-text-secondary">{currentThought}</p>
              </motion.div>
            )}

            {/* Skeleton preview of expected result */}
            <div className="space-y-3 pt-2">
              <p className="text-xs text-text-muted font-medium uppercase tracking-wide">
                Prévia do resultado
              </p>
              <div className="p-3 bg-white/5 rounded-lg border border-white/10 space-y-3">
                {/* Sheet skeleton */}
                <div className="flex items-center gap-2">
                  <Skeleton className="h-4 w-4 rounded" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16 ml-auto" />
                </div>
                {/* Column skeletons */}
                <div className="grid grid-cols-3 gap-2">
                  <Skeleton className="h-8 rounded" />
                  <Skeleton className="h-8 rounded" />
                  <Skeleton className="h-8 rounded" />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Skeleton className="h-8 rounded" />
                  <Skeleton className="h-8 rounded" />
                  <Skeleton className="h-8 rounded" />
                </div>
                {/* Actions skeleton */}
                <div className="flex gap-2 pt-2">
                  <Skeleton className="h-9 flex-1 rounded-lg" />
                  <Skeleton className="h-9 w-24 rounded-lg" />
                </div>
              </div>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Error state
  if (state.stage === 'error') {
    return (
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <GlassCardTitle>Erro na Análise</GlassCardTitle>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-4">
            {/* NEXO Explanation for error state */}
            <NexoExplanation
              summary={ERROR_EXPLANATION.summary}
              details={ERROR_EXPLANATION.details}
              action={ERROR_EXPLANATION.action}
              variant="warning"
            />

            {/* BUG-039: Show DebugAnalysisPanel if debug analysis available */}
            {state.debugAnalysis ? (
              <DebugAnalysisPanel
                analysis={state.debugAnalysis}
                defaultExpanded={true}
                className="my-4"
              />
            ) : (
              <p className="text-sm text-red-400">{state.error}</p>
            )}

            <Button variant="outline" onClick={onCancel}>
              Tentar novamente
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Success state - import completed successfully
  if (state.stage === 'complete') {
    return (
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15 }}
              className="p-1.5 rounded-lg bg-gradient-to-br from-green-500 to-cyan-500"
            >
              <CheckCircle2 className="w-5 h-5 text-white" />
            </motion.div>
            <GlassCardTitle>Importação Concluída!</GlassCardTitle>
          </div>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-6">
            {/* Success animation and message */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-6"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
                className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-green-500/20 to-cyan-500/20 flex items-center justify-center"
              >
                <CheckCircle2 className="w-10 h-10 text-green-400" />
              </motion.div>

              <h3 className="text-xl font-semibold text-text-primary mb-2">
                Dados Importados com Sucesso!
              </h3>

              <p className="text-text-muted">
                {reviewSummary?.totalItems
                  ? `${reviewSummary.totalItems.toLocaleString()} itens foram adicionados às entradas pendentes`
                  : 'Os dados foram processados e estão aguardando revisão'}
              </p>
            </motion.div>

            {/* Summary card */}
            {reviewSummary && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="p-4 bg-white/5 rounded-lg border border-white/10 space-y-3"
              >
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
                  <div>
                    <p className="font-medium">{reviewSummary.filename}</p>
                    <p className="text-sm text-text-muted">
                      {reviewSummary.mainSheet}
                    </p>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4 pt-3 border-t border-white/10">
                  <div>
                    <p className="text-sm text-text-muted">Itens importados</p>
                    <p className="text-xl font-bold text-green-400">
                      {reviewSummary.totalItems.toLocaleString()}
                    </p>
                  </div>
                  {reviewSummary.projectName && (
                    <div>
                      <p className="text-sm text-text-muted">Projeto</p>
                      <p className="text-lg font-medium">{reviewSummary.projectName}</p>
                    </div>
                  )}
                </div>

                {/* New columns created (if any) */}
                {reviewSummary.newColumns && reviewSummary.newColumns.length > 0 && (
                  <div className="pt-3 border-t border-white/10">
                    <p className="text-sm text-text-muted mb-2 flex items-center gap-2">
                      <Columns3 className="w-4 h-4 text-purple-400" />
                      Novos campos criados:
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {reviewSummary.newColumns.map((col, i) => (
                        <Badge key={i} className="bg-purple-500/20 text-purple-400">
                          {col.name} ({col.inferredType})
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* NEXO Explanation */}
            <NexoExplanation
              summary={SUCCESS_EXPLANATION.summary}
              details={SUCCESS_EXPLANATION.details}
              action={SUCCESS_EXPLANATION.action}
              variant="success"
            />

            {/* Actions */}
            <div className="flex justify-center gap-3 pt-4">
              <Button
                onClick={onCancel}
                className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white"
              >
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Nova Importação
              </Button>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // Analysis complete - show results
  if (state.analysis) {
    return (
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Brain className="w-5 h-5 text-purple-400" />
              <GlassCardTitle>Análise NEXO</GlassCardTitle>
            </div>
            <Badge
              className={
                state.analysis.overallConfidence >= 0.8
                  ? 'bg-green-500/20 text-green-400'
                  : state.analysis.overallConfidence >= 0.5
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-red-500/20 text-red-400'
              }
            >
              {Math.round(state.analysis.overallConfidence * 100)}% confiança
            </Badge>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          <div className="space-y-6">
            {/* File info */}
            <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
              <FileSpreadsheet className="w-5 h-5 text-cyan-400" />
              <div>
                <p className="font-medium">{state.analysis.filename}</p>
                <p className="text-sm text-text-muted">
                  {state.analysis.detectedType.toUpperCase()} · {state.analysis.recommendedStrategy}
                </p>
              </div>
            </div>

            {/* Prior knowledge indicator */}
            {priorKnowledge && priorKnowledge.similar_episodes > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-gradient-to-r from-purple-500/10 to-cyan-500/10 rounded-lg border border-purple-500/20"
              >
                <div className="flex items-center gap-2 mb-3">
                  <History className="w-4 h-4 text-purple-400" />
                  <span className="font-medium text-sm">Conhecimento Prévio Encontrado</span>
                  <Badge className="bg-purple-500/20 text-purple-400 text-xs">
                    {priorKnowledge.similar_episodes} importações similares
                  </Badge>
                </div>

                {/* NEXO Explanation for prior knowledge */}
                <NexoExplanation
                  summary={getPriorKnowledgeExplanation(priorKnowledge.similar_episodes).summary}
                  details={getPriorKnowledgeExplanation(priorKnowledge.similar_episodes).details}
                  action={getPriorKnowledgeExplanation(priorKnowledge.similar_episodes).action}
                  variant="success"
                  compact
                />

                {/* Suggested mappings count */}
                {Object.keys(priorKnowledge.suggested_mappings).length > 0 && (
                  <div className="flex items-center gap-4 text-sm mb-2 mt-3">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-cyan-400" />
                      <span className="text-text-secondary">
                        {Object.keys(priorKnowledge.suggested_mappings).length} mapeamentos sugeridos
                      </span>
                    </div>
                    {priorKnowledge.confidence_boost && (
                      <Badge className="bg-green-500/20 text-green-400 text-xs">
                        +15% confiança
                      </Badge>
                    )}
                  </div>
                )}

                {/* Reflections from past imports */}
                {priorKnowledge.reflections.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-white/10">
                    <p className="text-xs text-text-muted mb-2 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      Aprendizados de importações anteriores:
                    </p>
                    <ul className="space-y-1">
                      {priorKnowledge.reflections.slice(0, 2).map((reflection, i) => (
                        <li key={i} className="text-xs text-text-secondary flex items-start gap-2">
                          <span className="text-purple-400">•</span>
                          {reflection}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </motion.div>
            )}

            {/* First time indicator */}
            {(!priorKnowledge || priorKnowledge.similar_episodes === 0) && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-3"
              >
                {/* NEXO Explanation for first-time import */}
                <NexoExplanation
                  summary={getPriorKnowledgeExplanation(0).summary}
                  details={getPriorKnowledgeExplanation(0).details}
                  action={getPriorKnowledgeExplanation(0).action}
                  variant="info"
                  compact
                />
              </motion.div>
            )}

            {/* Reasoning trace */}
            <ReasoningTrace steps={reasoningTrace} />

            {/* Sheet analysis */}
            {state.analysis.sheets.length > 0 && (
              <SheetAnalysis sheets={state.analysis.sheets} />
            )}

            {/* Column mappings */}
            {state.analysis.columnMappings.length > 0 && (
              <ColumnMappings mappings={state.analysis.columnMappings} />
            )}

            {/* Questions section */}
            {hasQuestions && (
              <QuestionPanel
                questions={state.questions}
                answers={state.answers}
                onAnswer={answerQuestion}
                onSubmit={handleSubmitAnswers}
                onSkip={handleSkipQuestions}
                isSubmitting={isSubmitting}
              />
            )}

            {/* Review section - HIL approval before import */}
            {isReviewing && reviewSummary && (
              <ImportReviewPanel
                reviewSummary={reviewSummary}
                userFeedback={state.userFeedback}
                onApprove={handleApproveAndImport}
                onBack={handleBackToQuestions}
                onCancel={onCancel}
                isSubmitting={isSubmitting}
              />
            )}

            {/* Ready to process - only show if reviewSummary exists
                FIX (January 2026): Added reviewSummary check to prevent showing
                button when the reviewing stage was skipped */}
            {isReadyToProcess && !hasQuestions && !isReviewing && reviewSummary && (
              <div className="flex justify-end gap-3 pt-4 border-t border-white/10">
                <Button variant="outline" onClick={onCancel}>
                  Cancelar
                </Button>
                <Button
                  onClick={handleContinue}
                  disabled={isSubmitting}
                  className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Preparando...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Continuar para importação
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        </GlassCardContent>
      </GlassCard>
    );
  }

  // No file yet
  return null;
}

export default SmartImportNexoPanel;
