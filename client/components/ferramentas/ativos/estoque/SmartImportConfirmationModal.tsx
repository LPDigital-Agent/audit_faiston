'use client';

// =============================================================================
// SmartImportConfirmationModal - SGA Inventory Module
// =============================================================================
// Apple TV-style frosted glass confirmation popup for Smart Import.
// Shows import summary and NEXO AI observations before DB commit.
//
// Design: Frosted dark glass effect (backdrop-blur + rgba background)
// Pattern: User must explicitly confirm before assets are committed
// =============================================================================

import { useState, useEffect, useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Check,
  AlertTriangle,
  Bot,
  Package,
  FileText,
  TrendingUp,
  Shield,
  Lightbulb,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SmartImportPreview } from '@/lib/ativos/smartImportTypes';
import type { NexoObservation } from '@/lib/ativos/nexoObservationTypes';
import {
  getRiskLevelColor,
  getRiskLevelLabel,
  DEFAULT_NEXO_OBSERVATION,
} from '@/lib/ativos/nexoObservationTypes';
import { generateImportObservations } from '@/services/sgaAgentcore';

// =============================================================================
// Types
// =============================================================================

interface SmartImportConfirmationModalProps {
  /** Whether the modal is open */
  open: boolean;
  /** Callback when modal should close */
  onOpenChange: (open: boolean) => void;
  /** The import preview data */
  preview: SmartImportPreview;
  /** Callback when user confirms the import */
  onConfirm: () => Promise<void>;
  /** Whether confirmation is in progress */
  isConfirming?: boolean;
}

// =============================================================================
// Helper Functions
// =============================================================================

function getSourceTypeLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    nf_xml: 'NF XML',
    nf_pdf: 'NF PDF',
    nf_image: 'Imagem NF',
    spreadsheet: 'Planilha',
    text: 'Texto/Manual',
    sap_export: 'Export SAP',
  };
  return labels[sourceType] || sourceType;
}

function getSourceTypeIcon(sourceType: string) {
  if (sourceType.startsWith('nf_')) return FileText;
  if (sourceType === 'spreadsheet') return Package;
  return FileText;
}

// =============================================================================
// Component
// =============================================================================

export function SmartImportConfirmationModal({
  open,
  onOpenChange,
  preview,
  onConfirm,
  isConfirming = false,
}: SmartImportConfirmationModalProps) {
  // State for NEXO observations
  const [observations, setObservations] = useState<NexoObservation | null>(null);
  const [isLoadingObservations, setIsLoadingObservations] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);

  // Fetch NEXO observations when modal opens
  useEffect(() => {
    if (open && !observations && !isLoadingObservations) {
      fetchObservations();
    }
  }, [open]);

  const fetchObservations = useCallback(async () => {
    setIsLoadingObservations(true);
    setObservationError(null);

    try {
      const response = await generateImportObservations(preview);
      if (response.data.success) {
        setObservations(response.data);
      } else {
        setObservations(DEFAULT_NEXO_OBSERVATION);
      }
    } catch (error) {
      console.error('[SmartImportConfirmationModal] Failed to fetch observations:', error);
      setObservationError('Nao foi possivel carregar observacoes do NEXO');
      setObservations(DEFAULT_NEXO_OBSERVATION);
    } finally {
      setIsLoadingObservations(false);
    }
  }, [preview]);

  const handleConfirm = async () => {
    await onConfirm();
    onOpenChange(false);
  };

  const handleClose = () => {
    if (!isConfirming) {
      onOpenChange(false);
    }
  };

  // Extract summary data from preview
  const itemsCount = 'items' in preview && Array.isArray(preview.items) ? preview.items.length : 0;
  const totalValue = 'total_value' in preview ? (preview as Record<string, unknown>).total_value as number | undefined : undefined;
  const supplierName = 'supplier' in preview && typeof preview.supplier === 'object' && preview.supplier !== null
    ? ((preview.supplier as Record<string, unknown>).name as string) || 'Nao informado'
    : 'Nao informado';
  const SourceIcon = getSourceTypeIcon(preview.source_type);

  return (
    <Dialog.Root open={open} onOpenChange={handleClose}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            {/* Overlay - Frosted Glass Effect */}
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="fixed inset-0 z-50 bg-[#151720]/85 backdrop-blur-[24px]"
              />
            </Dialog.Overlay>

            {/* Modal Content */}
            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className={cn(
                  'fixed left-1/2 top-1/2 z-50 w-full max-w-[540px] -translate-x-1/2 -translate-y-1/2',
                  'bg-[#1a1d28]/90 backdrop-blur-xl',
                  'border border-white/[0.06] rounded-2xl shadow-2xl',
                  'p-6 max-h-[90vh] overflow-y-auto'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <Dialog.Title className="text-xl font-semibold text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-[#960A9C]/20 to-[#2226C0]/20 border border-white/[0.04]">
                      <Check className="w-5 h-5 text-[#00FAFB]" />
                    </div>
                    Confirmar Importacao
                  </Dialog.Title>
                  <Dialog.Close asChild>
                    <button
                      className="p-2 rounded-lg hover:bg-white/5 transition-colors disabled:opacity-50"
                      disabled={isConfirming}
                      aria-label="Fechar"
                    >
                      <X className="w-5 h-5 text-gray-400" />
                    </button>
                  </Dialog.Close>
                </div>

                {/* Summary Section */}
                <div className="mb-6 p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
                    <Package className="w-4 h-4" />
                    Resumo da Importacao
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Fonte</p>
                      <p className="text-sm text-white flex items-center gap-2">
                        <SourceIcon className="w-4 h-4 text-[#00FAFB]" />
                        {getSourceTypeLabel(preview.source_type)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Itens</p>
                      <p className="text-sm text-white font-medium">{itemsCount} ativo(s)</p>
                    </div>
                    {totalValue !== undefined && (
                      <div>
                        <p className="text-xs text-gray-500 mb-1">Valor Total</p>
                        <p className="text-sm text-white font-medium">
                          R$ {totalValue.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                        </p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Fornecedor</p>
                      <p className="text-sm text-white truncate">{supplierName}</p>
                    </div>
                  </div>
                </div>

                {/* NEXO AI Observations Section */}
                <div className="mb-6 p-4 rounded-xl bg-gradient-to-r from-[#960A9C]/10 to-[#2226C0]/10 border border-white/[0.04]">
                  <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
                    <Bot className="w-4 h-4 text-[#A855F7]" />
                    Observacoes do NEXO
                  </h3>

                  {isLoadingObservations ? (
                    <div className="flex items-center gap-3 py-4">
                      <Loader2 className="w-5 h-5 text-[#A855F7] animate-spin" />
                      <p className="text-sm text-gray-400">Analisando dados...</p>
                    </div>
                  ) : observations ? (
                    <div className="space-y-4">
                      {/* Confidence Score */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Shield className="w-4 h-4 text-gray-400" />
                          <span className="text-sm text-gray-400">Confianca</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${observations.confidence.overall}%` }}
                              transition={{ duration: 0.5, delay: 0.2 }}
                              className={cn(
                                'h-full rounded-full',
                                observations.confidence.overall >= 75
                                  ? 'bg-[#00FAFB]'
                                  : observations.confidence.overall >= 50
                                    ? 'bg-amber-400'
                                    : 'bg-[#FD5665]'
                              )}
                            />
                          </div>
                          <span className="text-sm font-medium text-white">
                            {observations.confidence.overall}%
                          </span>
                          <span className={cn('text-xs', getRiskLevelColor(observations.confidence.risk_level))}>
                            ({getRiskLevelLabel(observations.confidence.risk_level)})
                          </span>
                        </div>
                      </div>

                      {/* AI Commentary */}
                      <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.02]">
                        <p className="text-sm text-gray-300 leading-relaxed">
                          {observations.ai_commentary}
                        </p>
                      </div>

                      {/* Patterns & Suggestions */}
                      {(observations.observations.patterns.length > 0 ||
                        observations.observations.suggestions.length > 0) && (
                        <div className="grid grid-cols-2 gap-3">
                          {/* Patterns */}
                          {observations.observations.patterns.length > 0 && (
                            <div className="p-3 rounded-lg bg-white/[0.02]">
                              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                                <TrendingUp className="w-3 h-3" />
                                Padroes Detectados
                              </p>
                              <ul className="space-y-1">
                                {observations.observations.patterns.slice(0, 3).map((pattern, i) => (
                                  <li key={i} className="text-xs text-gray-400 truncate">
                                    {pattern}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Suggestions */}
                          {observations.observations.suggestions.length > 0 && (
                            <div className="p-3 rounded-lg bg-white/[0.02]">
                              <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
                                <Lightbulb className="w-3 h-3" />
                                Sugestoes
                              </p>
                              <ul className="space-y-1">
                                {observations.observations.suggestions.slice(0, 3).map((suggestion, i) => (
                                  <li key={i} className="text-xs text-gray-400 truncate">
                                    {suggestion}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Warnings */}
                      {observations.observations.warnings.length > 0 && (
                        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                          <p className="text-xs text-amber-400 mb-2 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            Alertas
                          </p>
                          <ul className="space-y-1">
                            {observations.observations.warnings.map((warning, i) => (
                              <li key={i} className="text-xs text-amber-300">
                                {warning}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : observationError ? (
                    <div className="flex items-center gap-3 py-4 text-amber-400">
                      <AlertTriangle className="w-5 h-5" />
                      <p className="text-sm">{observationError}</p>
                    </div>
                  ) : null}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end gap-3">
                  <Button
                    variant="outline"
                    onClick={handleClose}
                    disabled={isConfirming}
                    className="bg-transparent border-white/10 text-gray-400 hover:bg-white/5 hover:text-white"
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleConfirm}
                    disabled={isConfirming || isLoadingObservations}
                    className={cn(
                      'bg-gradient-to-r from-[#00FAFB] to-[#2226C0]',
                      'text-white font-medium',
                      'hover:opacity-90 transition-opacity',
                      'disabled:opacity-50'
                    )}
                  >
                    {isConfirming ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Confirmando...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Confirmar Importacao
                      </>
                    )}
                  </Button>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}

export default SmartImportConfirmationModal;
