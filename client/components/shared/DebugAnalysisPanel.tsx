"use client";

// =============================================================================
// Debug Analysis Panel - Faiston NEXO
// =============================================================================
// Displays enriched error analysis from the Debug Agent.
// Shows technical explanations, root causes, debugging steps, and suggestions.
//
// CRITICAL-001 FIX: This component enables frontend display of debug_analysis
// returned by the Debug Agent through the DebugHook error interception system.
// =============================================================================

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from "./glass-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type {
  DebugAnalysis,
  DebugRootCause,
  DebugDocumentationLink,
  DebugSimilarPattern,
} from "@/utils/agentcoreResponse";
import {
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  ArrowRight,
  ExternalLink,
  FileText,
  Lightbulb,
  Target,
  BookOpen,
  History,
  XCircle,
} from "lucide-react";

// =============================================================================
// Types
// =============================================================================

export interface DebugAnalysisPanelProps {
  /** The debug analysis data from Debug Agent */
  analysis: DebugAnalysis;
  /** Callback when user clicks the suggested action button */
  onAction?: (action: DebugAnalysis["suggested_action"]) => void;
  /** Additional CSS classes */
  className?: string;
  /** Whether to start expanded (default: true) */
  defaultExpanded?: boolean;
}

// =============================================================================
// Helper Components
// =============================================================================

/**
 * Confidence indicator bar with color coding
 */
function ConfidenceBar({
  confidence,
  className,
}: {
  confidence: number;
  className?: string;
}) {
  const percentage = Math.round(confidence * 100);
  const colorClass =
    percentage >= 80
      ? "bg-green-500"
      : percentage >= 50
      ? "bg-yellow-500"
      : "bg-red-500";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-text-secondary w-10">{percentage}%</span>
    </div>
  );
}

/**
 * Source badge for root cause analysis
 */
function SourceBadge({ source }: { source: DebugRootCause["source"] }) {
  const config = {
    memory_pattern: {
      label: "Padrão",
      icon: History,
      className: "bg-purple-500/20 text-purple-300 border-purple-500/30",
    },
    documentation: {
      label: "Docs",
      icon: BookOpen,
      className: "bg-blue-500/20 text-blue-300 border-blue-500/30",
    },
    inference: {
      label: "Inferência",
      icon: Lightbulb,
      className: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
    },
  };

  const { label, icon: Icon, className } = config[source];

  return (
    <Badge variant="outline" className={cn("text-xs", className)}>
      <Icon className="w-3 h-3 mr-1" />
      {label}
    </Badge>
  );
}

/**
 * Action badge based on suggested action
 */
function ActionBadge({
  action,
}: {
  action: DebugAnalysis["suggested_action"];
}) {
  const config = {
    retry: {
      label: "Tentar Novamente",
      icon: RefreshCw,
      className: "bg-green-500/20 text-green-300 border-green-500/30",
    },
    fallback: {
      label: "Alternativa",
      icon: ArrowRight,
      className: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
    },
    escalate: {
      label: "Escalar",
      icon: AlertTriangle,
      className: "bg-orange-500/20 text-orange-300 border-orange-500/30",
    },
    abort: {
      label: "Abortar",
      icon: XCircle,
      className: "bg-red-500/20 text-red-300 border-red-500/30",
    },
  };

  const { label, icon: Icon, className } = config[action];

  return (
    <Badge variant="outline" className={cn("text-xs", className)}>
      <Icon className="w-3 h-3 mr-1" />
      {label}
    </Badge>
  );
}

// =============================================================================
// Section Components
// =============================================================================

/**
 * Collapsible section wrapper
 */
function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultExpanded = false,
  count,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultExpanded?: boolean;
  count?: number;
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="border-t border-white/10 pt-3 mt-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full text-left group"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-primary-400" />
          <span className="text-sm font-medium text-text-primary">{title}</span>
          {count !== undefined && (
            <Badge variant="secondary" className="text-xs">
              {count}
            </Badge>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-text-secondary group-hover:text-text-primary transition-colors" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-secondary group-hover:text-text-primary transition-colors" />
        )}
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pt-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * Root causes section
 */
function RootCausesSection({ causes }: { causes: DebugRootCause[] }) {
  return (
    <div className="space-y-3">
      {causes.map((cause, index) => (
        <div
          key={index}
          className="p-3 rounded-lg bg-white/5 border border-white/10"
        >
          <div className="flex items-start justify-between gap-2 mb-2">
            <span className="text-sm text-text-primary flex-1">
              {cause.cause}
            </span>
            <SourceBadge source={cause.source} />
          </div>
          <ConfidenceBar confidence={cause.confidence} className="mb-2" />
          {cause.evidence.length > 0 && (
            <div className="mt-2 pt-2 border-t border-white/5">
              <span className="text-xs text-text-secondary block mb-1">
                Evidências:
              </span>
              <ul className="list-disc list-inside text-xs text-text-secondary space-y-0.5">
                {cause.evidence.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Debugging steps section
 */
function DebuggingStepsSection({ steps }: { steps: string[] }) {
  return (
    <ol className="list-decimal list-inside space-y-2">
      {steps.map((step, index) => (
        <li key={index} className="text-sm text-text-secondary">
          <span className="ml-1">{step}</span>
        </li>
      ))}
    </ol>
  );
}

/**
 * Documentation links section
 */
function DocumentationSection({ links }: { links: DebugDocumentationLink[] }) {
  return (
    <div className="space-y-2">
      {links.map((link, index) => (
        <a
          key={index}
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-start gap-2 p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 hover:border-primary-500/50 transition-colors group"
        >
          <FileText className="w-4 h-4 text-primary-400 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-sm text-text-primary block truncate group-hover:text-primary-300 transition-colors">
              {link.title}
            </span>
            <span className="text-xs text-text-secondary">{link.relevance}</span>
          </div>
          <ExternalLink className="w-3 h-3 text-text-secondary group-hover:text-primary-400 transition-colors shrink-0" />
        </a>
      ))}
    </div>
  );
}

/**
 * Similar patterns section
 */
function SimilarPatternsSection({
  patterns,
}: {
  patterns: DebugSimilarPattern[];
}) {
  return (
    <div className="space-y-2">
      {patterns.map((pattern, index) => (
        <div
          key={index}
          className="p-3 rounded-lg bg-white/5 border border-white/10"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-text-secondary font-mono">
              {pattern.pattern_id}
            </span>
            <Badge variant="outline" className="text-xs">
              {Math.round(pattern.similarity * 100)}% similar
            </Badge>
          </div>
          <p className="text-sm text-text-primary">{pattern.resolution}</p>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// Main Component
// =============================================================================

/**
 * DebugAnalysisPanel - Displays enriched error analysis from Debug Agent
 *
 * This component renders the complete debug analysis including:
 * - Error type badge with recoverable indicator
 * - Technical explanation (in pt-BR)
 * - Root causes with confidence levels
 * - Step-by-step debugging instructions
 * - Relevant documentation links
 * - Similar patterns from memory
 * - Suggested action button
 *
 * @example
 * ```tsx
 * <DebugAnalysisPanel
 *   analysis={errorResponse.debug_analysis}
 *   onAction={(action) => {
 *     if (action === 'retry') handleRetry();
 *     else if (action === 'escalate') openSupportTicket();
 *   }}
 * />
 * ```
 */
export function DebugAnalysisPanel({
  analysis,
  onAction,
  className,
  defaultExpanded = true,
}: DebugAnalysisPanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const actionConfig = {
    retry: {
      label: "Tentar Novamente",
      icon: RefreshCw,
      variant: "default" as const,
    },
    fallback: {
      label: "Usar Alternativa",
      icon: ArrowRight,
      variant: "secondary" as const,
    },
    escalate: {
      label: "Escalar para Suporte",
      icon: AlertTriangle,
      variant: "secondary" as const,
    },
    abort: {
      label: "Cancelar Operação",
      icon: XCircle,
      variant: "destructive" as const,
    },
  };

  const actionInfo = actionConfig[analysis.suggested_action];

  return (
    <GlassCard
      className={cn("border-red-500/30", className)}
      elevated
      padding="md"
    >
      {/* Header */}
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <GlassCardTitle className="text-base">Análise de Erro</GlassCardTitle>
        </div>
        <div className="flex items-center gap-2">
          {analysis.recoverable && (
            <Badge
              variant="outline"
              className="bg-green-500/20 text-green-300 border-green-500/30"
            >
              <CheckCircle className="w-3 h-3 mr-1" />
              Recuperável
            </Badge>
          )}
          <Badge variant="destructive">{analysis.error_type}</Badge>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:bg-white/10 rounded transition-colors"
          >
            {isExpanded ? (
              <ChevronUp className="w-4 h-4 text-text-secondary" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-secondary" />
            )}
          </button>
        </div>
      </GlassCardHeader>

      {/* Collapsible Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <GlassCardContent>
              {/* Technical Explanation */}
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 mb-4">
                <p className="text-sm text-text-primary leading-relaxed">
                  {analysis.technical_explanation}
                </p>
              </div>

              {/* Suggested Action */}
              <div className="flex items-center justify-between mb-4 p-3 rounded-lg bg-white/5 border border-white/10">
                <div className="flex items-center gap-2">
                  <Target className="w-4 h-4 text-primary-400" />
                  <span className="text-sm text-text-secondary">
                    Ação Recomendada:
                  </span>
                  <ActionBadge action={analysis.suggested_action} />
                </div>
                {onAction && (
                  <Button
                    variant={actionInfo.variant}
                    size="sm"
                    onClick={() => onAction(analysis.suggested_action)}
                    className="gap-1"
                  >
                    <actionInfo.icon className="w-3 h-3" />
                    {actionInfo.label}
                  </Button>
                )}
              </div>

              {/* Root Causes Section */}
              {analysis.root_causes.length > 0 && (
                <CollapsibleSection
                  title="Possíveis Causas"
                  icon={AlertTriangle}
                  defaultExpanded={true}
                  count={analysis.root_causes.length}
                >
                  <RootCausesSection causes={analysis.root_causes} />
                </CollapsibleSection>
              )}

              {/* Debugging Steps Section */}
              {analysis.debugging_steps.length > 0 && (
                <CollapsibleSection
                  title="Passos de Debug"
                  icon={Lightbulb}
                  defaultExpanded={true}
                  count={analysis.debugging_steps.length}
                >
                  <DebuggingStepsSection steps={analysis.debugging_steps} />
                </CollapsibleSection>
              )}

              {/* Documentation Links Section */}
              {analysis.documentation_links.length > 0 && (
                <CollapsibleSection
                  title="Documentação Relacionada"
                  icon={BookOpen}
                  defaultExpanded={false}
                  count={analysis.documentation_links.length}
                >
                  <DocumentationSection links={analysis.documentation_links} />
                </CollapsibleSection>
              )}

              {/* Similar Patterns Section */}
              {analysis.similar_patterns.length > 0 && (
                <CollapsibleSection
                  title="Padrões Similares"
                  icon={History}
                  defaultExpanded={false}
                  count={analysis.similar_patterns.length}
                >
                  <SimilarPatternsSection patterns={analysis.similar_patterns} />
                </CollapsibleSection>
              )}
            </GlassCardContent>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  );
}

export default DebugAnalysisPanel;
