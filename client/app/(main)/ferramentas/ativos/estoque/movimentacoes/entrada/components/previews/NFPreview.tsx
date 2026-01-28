'use client';

// =============================================================================
// NFPreview - NF Extraction Preview Component
// =============================================================================
// Displays extracted data from NF (XML, PDF, or Image via OCR).
// Shows confidence score, supplier info, and extracted items.
// =============================================================================

import { motion } from 'framer-motion';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  FileText,
  Package,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Calendar,
  Hash,
  FolderPlus,
  X,
} from 'lucide-react';
import type { NFImportResult } from '@/lib/ativos/smartImportTypes';
import { requiresHILReview } from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Types
// =============================================================================

interface NFPreviewProps {
  preview: NFImportResult;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  isConfirming?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function NFPreview({
  preview,
  onConfirm,
  onCancel,
  isConfirming = false,
}: NFPreviewProps) {
  const { extraction, confidence_score } = preview;
  const needsHIL = requiresHILReview(preview);

  // Get source type label
  const sourceTypeLabel = {
    nf_xml: 'XML',
    nf_pdf: 'PDF',
    nf_image: 'Imagem (OCR)',
  }[preview.source_type] || 'Desconhecido';

  // Confidence color
  const getConfidenceColor = (score: number) => {
    if (score >= 0.9) return 'bg-green-500/20 text-green-400';
    if (score >= 0.7) return 'bg-yellow-500/20 text-yellow-400';
    return 'bg-red-500/20 text-red-400';
  };

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-light" />
            <GlassCardTitle>Dados Extraidos</GlassCardTitle>
            <Badge variant="outline" className="text-xs">
              {sourceTypeLabel}
            </Badge>
          </div>
          {confidence_score && (
            <Badge className={getConfidenceColor(confidence_score.overall)}>
              Confianca: {Math.round(confidence_score.overall * 100)}%
            </Badge>
          )}
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="space-y-6">
          {/* NF Header Info */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-white/5 rounded-lg">
            <div>
              <div className="flex items-center gap-1 text-xs text-text-muted mb-1">
                <Hash className="w-3 h-3" />
                Numero NF
              </div>
              <p className="text-sm font-medium text-text-primary">
                {extraction.nf_number || '-'}
              </p>
            </div>
            <div>
              <div className="flex items-center gap-1 text-xs text-text-muted mb-1">
                Serie
              </div>
              <p className="text-sm font-medium text-text-primary">
                {extraction.nf_series || '-'}
              </p>
            </div>
            <div>
              <div className="flex items-center gap-1 text-xs text-text-muted mb-1">
                <Building2 className="w-3 h-3" />
                Fornecedor
              </div>
              <p className="text-sm font-medium text-text-primary truncate">
                {extraction.supplier_name || '-'}
              </p>
            </div>
            <div>
              <div className="flex items-center gap-1 text-xs text-text-muted mb-1">
                <Calendar className="w-3 h-3" />
                Data Emissao
              </div>
              <p className="text-sm font-medium text-text-primary">
                {extraction.issue_date
                  ? new Date(extraction.issue_date).toLocaleDateString('pt-BR')
                  : '-'}
              </p>
            </div>
          </div>

          {/* Extraction Warnings */}
          {extraction.extraction_warnings && extraction.extraction_warnings.length > 0 && (
            <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <p className="text-xs font-medium text-yellow-400 mb-2">Avisos da Extracao:</p>
              <ul className="text-xs text-yellow-400/80 space-y-1">
                {extraction.extraction_warnings.map((warning, i) => (
                  <li key={i}>- {warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Items List */}
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
              <Package className="w-4 h-4 text-blue-light" />
              Itens ({extraction.items?.length || 0})
            </h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {(extraction.items || []).map((item, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="flex items-center gap-4 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-blue-mid/20 flex items-center justify-center shrink-0">
                    <Package className="w-4 h-4 text-blue-light" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary truncate">{item.description}</p>
                    <p className="text-xs text-text-muted">
                      Codigo: {item.product_code || '-'} | NCM: {item.ncm_code || '-'}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-medium text-text-primary">
                      Qtd: {item.quantity} {item.unit_of_measure}
                    </p>
                    <p className="text-xs text-text-muted">
                      R$ {item.unit_value?.toFixed(2) || '0.00'}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Total Value */}
          {extraction.total_value && (
            <div className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-mid/10 to-magenta-mid/10 rounded-lg">
              <span className="text-sm text-text-muted">Valor Total da NF</span>
              <span className="text-lg font-bold text-text-primary">
                R$ {extraction.total_value.toFixed(2)}
              </span>
            </div>
          )}

          {/* Review/HIL Warning */}
          {needsHIL && (
            <div className="flex items-start gap-3 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-yellow-400">
                  Revisao Necessaria
                </p>
                <p className="text-xs text-yellow-400/80 mt-1">
                  A confianca da extracao esta abaixo do limite. Por favor, revise os dados antes de confirmar.
                </p>
              </div>
            </div>
          )}

          {/* Project Required Warning */}
          {preview.requires_hil && (
            <div className="flex items-start gap-3 p-4 bg-orange-500/20 border border-orange-500/30 rounded-lg">
              <FolderPlus className="w-5 h-5 text-orange-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-orange-400">
                  Projeto Nao Atribuido
                </p>
                <p className="text-xs text-orange-400/80 mt-1">
                  Esta entrada sera criada sem projeto. Voce podera atribuir um projeto depois.
                </p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <Button
              variant="outline"
              onClick={onCancel}
              className="flex-1"
              disabled={isConfirming}
            >
              <X className="w-4 h-4 mr-2" />
              Cancelar
            </Button>
            <Button
              onClick={onConfirm}
              className="flex-1 bg-gradient-to-r from-blue-mid to-green-500 hover:from-blue-mid/80 hover:to-green-500/80 text-white"
              disabled={isConfirming}
            >
              {isConfirming ? (
                <>Confirmando...</>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Confirmar Entrada
                </>
              )}
            </Button>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
