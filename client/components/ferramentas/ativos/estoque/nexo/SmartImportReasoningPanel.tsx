'use client';

// =============================================================================
// SmartImportReasoningPanel - NEXO Reasoning Visualization
// =============================================================================
// Dedicated panel for displaying NEXO's AI reasoning process.
// Shows the ReAct pattern steps with visual hierarchy and timeline.
//
// Philosophy: Transparency builds trust - show HOW NEXO is thinking
//
// Features:
// - Timeline view of reasoning steps
// - Expandable details for each step
// - Memory/learning indicators
// - Confidence evolution graph
// =============================================================================

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Eye,
  Play,
  Lightbulb,
  MessageCircleQuestion,
  Database,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Sparkles,
  History,
  TrendingUp,
  BookOpen,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import type { NexoReasoningStep } from '@/hooks/ativos/useSmartImportNexo';

// =============================================================================
// Types
// =============================================================================

interface SmartImportReasoningPanelProps {
  steps: NexoReasoningStep[];
  isLive?: boolean;
  showTimeline?: boolean;
  showLearningIndicators?: boolean;
  compact?: boolean;
  className?: string;
}

interface PriorKnowledge {
  similar_episodes: number;
  suggested_mappings: Record<string, string>;
  confidence_boost: boolean;
  reflections: string[];
}

// =============================================================================
// Constants
// =============================================================================

const STEP_CONFIG: Record<NexoReasoningStep['type'], {
  icon: typeof Brain;
  color: string;
  bgColor: string;
  label: string;
  labelPt: string;
}> = {
  thought: {
    icon: Brain,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/20',
    label: 'THOUGHT',
    labelPt: 'Pensamento',
  },
  action: {
    icon: Play,
    color: 'text-cyan-400',
    bgColor: 'bg-cyan-500/20',
    label: 'ACTION',
    labelPt: 'Ação',
  },
  observation: {
    icon: Eye,
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
    label: 'OBSERVATION',
    labelPt: 'Observação',
  },
};

// =============================================================================
// Sub-Components
// =============================================================================

/**
 * Single reasoning step in timeline view.
 */
function ReasoningStepItem({
  step,
  index,
  isLast,
  isLive,
}: {
  step: NexoReasoningStep;
  index: number;
  isLast: boolean;
  isLive?: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const config = STEP_CONFIG[step.type];
  const Icon = config.icon;

  // Check if this step involves learning/memory
  const isLearningStep = step.tool === 'learning_agent' || step.tool === 'episodic_memory';
  const isMappingStep = step.content.toLowerCase().includes('mapeamento') ||
    step.content.toLowerCase().includes('mapping');

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="relative"
    >
      {/* Timeline connector */}
      {!isLast && (
        <div className="absolute left-[19px] top-10 w-0.5 h-full bg-white/10" />
      )}

      <div className="flex gap-3">
        {/* Step indicator */}
        <div className="relative">
          <div
            className={`
              w-10 h-10 rounded-full flex items-center justify-center
              ${config.bgColor} border border-white/10
              ${isLive && isLast ? 'animate-pulse' : ''}
            `}
          >
            <Icon className={`w-5 h-5 ${config.color}`} />
          </div>
          {isLearningStep && (
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-purple-500 rounded-full flex items-center justify-center">
              <Database className="w-2.5 h-2.5 text-white" />
            </div>
          )}
        </div>

        {/* Step content */}
        <div className="flex-1 pb-4">
          <div
            className="cursor-pointer"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <div className="flex items-center gap-2">
              <Badge className={`${config.bgColor} ${config.color} text-xs`}>
                {config.labelPt}
              </Badge>
              {step.tool && (
                <Badge variant="outline" className="text-xs">
                  {step.tool}
                </Badge>
              )}
              {isLearningStep && (
                <Badge className="bg-purple-500/20 text-purple-400 text-xs">
                  <Database className="w-3 h-3 mr-1" />
                  Memória
                </Badge>
              )}
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-text-muted ml-auto" />
              ) : (
                <ChevronRight className="w-4 h-4 text-text-muted ml-auto" />
              )}
            </div>

            <p className="text-sm text-text-secondary mt-1 line-clamp-2">
              {step.content}
            </p>
          </div>

          {/* Expanded details */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-3 space-y-2"
              >
                <div className="p-3 bg-white/5 rounded-lg border border-white/10 text-sm">
                  <p className="text-text-primary whitespace-pre-wrap">
                    {step.content}
                  </p>

                  {step.result && (
                    <div className="mt-2 pt-2 border-t border-white/10">
                      <p className="text-xs text-text-muted mb-1">Resultado:</p>
                      <p className="text-text-secondary">{step.result}</p>
                    </div>
                  )}
                </div>

                {isMappingStep && (
                  <div className="flex items-center gap-2 text-xs text-text-muted">
                    <TrendingUp className="w-3 h-3" />
                    <span>Este mapeamento será salvo para importações futuras</span>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}

/**
 * Prior knowledge indicator showing learned patterns.
 */
function PriorKnowledgeIndicator({
  knowledge,
}: {
  knowledge: PriorKnowledge | null;
}) {
  if (!knowledge || knowledge.similar_episodes === 0) {
    return (
      <div className="flex items-center gap-2 p-3 bg-white/5 rounded-lg border border-white/10">
        <Sparkles className="w-4 h-4 text-text-muted" />
        <span className="text-sm text-text-muted">
          Primeira vez analisando este tipo de arquivo
        </span>
      </div>
    );
  }

  const mappingCount = Object.keys(knowledge.suggested_mappings).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <History className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-medium">Conhecimento Prévio</span>
        <Badge className="bg-purple-500/20 text-purple-400 text-xs">
          {knowledge.similar_episodes} importações similares
        </Badge>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="p-2 bg-white/5 rounded border border-white/10">
          <p className="text-xs text-text-muted">Mapeamentos sugeridos</p>
          <p className="text-lg font-semibold text-cyan-400">{mappingCount}</p>
        </div>
        <div className="p-2 bg-white/5 rounded border border-white/10">
          <p className="text-xs text-text-muted">Confiança extra</p>
          <p className="text-lg font-semibold text-green-400">
            {knowledge.confidence_boost ? '+15%' : '—'}
          </p>
        </div>
      </div>

      {knowledge.reflections.length > 0 && (
        <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/20">
          <div className="flex items-center gap-2 mb-2">
            <BookOpen className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-medium text-purple-400">
              Aprendizados anteriores:
            </span>
          </div>
          <ul className="space-y-1">
            {knowledge.reflections.slice(0, 3).map((reflection, i) => (
              <li key={i} className="text-xs text-text-secondary flex items-start gap-2">
                <span className="text-purple-400">•</span>
                {reflection}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Compact inline view of reasoning.
 */
function CompactReasoningView({ steps }: { steps: NexoReasoningStep[] }) {
  const lastSteps = steps.slice(-3);

  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-2">
      {lastSteps.map((step, index) => {
        const config = STEP_CONFIG[step.type];
        const Icon = config.icon;

        return (
          <motion.div
            key={index}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded-full
              ${config.bgColor} border border-white/10 whitespace-nowrap
            `}
          >
            <Icon className={`w-3 h-3 ${config.color}`} />
            <span className="text-xs text-text-secondary truncate max-w-32">
              {step.content.slice(0, 40)}...
            </span>
          </motion.div>
        );
      })}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

export function SmartImportReasoningPanel({
  steps,
  isLive = false,
  showTimeline = true,
  showLearningIndicators = true,
  compact = false,
  className = '',
}: SmartImportReasoningPanelProps) {
  const [priorKnowledge] = useState<PriorKnowledge | null>(null);

  // Group steps by phase
  const phaseGroups = useMemo(() => {
    const groups: {
      observe: NexoReasoningStep[];
      think: NexoReasoningStep[];
      ask: NexoReasoningStep[];
      learn: NexoReasoningStep[];
      act: NexoReasoningStep[];
    } = {
      observe: [],
      think: [],
      ask: [],
      learn: [],
      act: [],
    };

    steps.forEach(step => {
      if (step.tool === 'sheet_analyzer') {
        groups.observe.push(step);
      } else if (step.type === 'thought') {
        groups.think.push(step);
      } else if (step.content.toLowerCase().includes('pergunt')) {
        groups.ask.push(step);
      } else if (step.tool === 'learning_agent' || step.tool === 'episodic_memory') {
        groups.learn.push(step);
      } else {
        groups.act.push(step);
      }
    });

    return groups;
  }, [steps]);

  // Count steps by type
  const stepCounts = useMemo(() => ({
    thought: steps.filter(s => s.type === 'thought').length,
    action: steps.filter(s => s.type === 'action').length,
    observation: steps.filter(s => s.type === 'observation').length,
  }), [steps]);

  if (steps.length === 0) {
    return null;
  }

  // Compact mode
  if (compact) {
    return (
      <div className={className}>
        <div className="flex items-center gap-2 mb-2">
          <Lightbulb className="w-4 h-4 text-purple-400" />
          <span className="text-sm text-text-muted">NEXO pensando...</span>
        </div>
        <CompactReasoningView steps={steps} />
      </div>
    );
  }

  return (
    <GlassCard className={className}>
      <GlassCardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-400" />
            <GlassCardTitle>Raciocínio NEXO</GlassCardTitle>
            {isLive && (
              <Badge className="bg-green-500/20 text-green-400 animate-pulse">
                <span className="w-2 h-2 bg-green-400 rounded-full mr-1.5" />
                Ao vivo
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              <Brain className="w-3 h-3 mr-1 text-purple-400" />
              {stepCounts.thought}
            </Badge>
            <Badge variant="outline" className="text-xs">
              <Play className="w-3 h-3 mr-1 text-cyan-400" />
              {stepCounts.action}
            </Badge>
            <Badge variant="outline" className="text-xs">
              <Eye className="w-3 h-3 mr-1 text-green-400" />
              {stepCounts.observation}
            </Badge>
          </div>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="space-y-6">
          {/* Prior knowledge indicator */}
          {showLearningIndicators && (
            <PriorKnowledgeIndicator knowledge={priorKnowledge} />
          )}

          {/* ReAct phases indicator */}
          <div className="flex items-center justify-between p-2 bg-white/5 rounded-lg">
            {[
              { key: 'observe', label: 'OBSERVE', icon: Eye, count: phaseGroups.observe.length },
              { key: 'think', label: 'THINK', icon: Brain, count: phaseGroups.think.length },
              { key: 'ask', label: 'ASK', icon: MessageCircleQuestion, count: phaseGroups.ask.length },
              { key: 'learn', label: 'LEARN', icon: Database, count: phaseGroups.learn.length },
              { key: 'act', label: 'ACT', icon: CheckCircle2, count: phaseGroups.act.length },
            ].map((phase) => {
              const Icon = phase.icon;
              const isActive = phase.count > 0;

              return (
                <div
                  key={phase.key}
                  className={`
                    flex flex-col items-center gap-1 px-3 py-2 rounded
                    ${isActive ? 'bg-white/5' : 'opacity-50'}
                  `}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-purple-400' : 'text-text-muted'}`} />
                  <span className="text-[10px] font-medium text-text-muted">
                    {phase.label}
                  </span>
                  {isActive && (
                    <Badge className="text-[10px] bg-white/10">
                      {phase.count}
                    </Badge>
                  )}
                </div>
              );
            })}
          </div>

          {/* Timeline view */}
          {showTimeline && (
            <div className="space-y-2">
              {steps.map((step, index) => (
                <ReasoningStepItem
                  key={index}
                  step={step}
                  index={index}
                  isLast={index === steps.length - 1}
                  isLive={isLive}
                />
              ))}
            </div>
          )}

          {/* Learning footer */}
          {showLearningIndicators && steps.some(s => s.tool === 'learning_agent') && (
            <div className="flex items-center gap-2 p-3 bg-gradient-to-r from-purple-500/10 to-cyan-500/10 rounded-lg border border-purple-500/20">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span className="text-sm text-text-secondary">
                NEXO está aprendendo com esta importação para melhorar no futuro
              </span>
            </div>
          )}
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}

export default SmartImportReasoningPanel;
