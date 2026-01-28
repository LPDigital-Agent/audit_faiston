'use client';

// =============================================================================
// SpreadsheetPreview - CSV/XLSX Import Preview Component
// =============================================================================
// Displays column mappings and sample data from spreadsheet imports.
// Shows match rate and allows column mapping adjustments.
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
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  CheckCircle2,
  AlertTriangle,
  FileSpreadsheet,
  Columns,
  ArrowRight,
  X,
  Check,
  HelpCircle,
} from 'lucide-react';
import type { SpreadsheetImportResult } from '@/lib/ativos/smartImportTypes';
import { requiresHILReview } from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Types
// =============================================================================

interface SpreadsheetPreviewProps {
  preview: SpreadsheetImportResult;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  isConfirming?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function SpreadsheetPreview({
  preview,
  onConfirm,
  onCancel,
  isConfirming = false,
}: SpreadsheetPreviewProps) {
  const { stats, column_mappings, matched_rows, unmatched_rows, confidence_score } = preview;
  const needsHIL = requiresHILReview(preview);

  // Confidence badge color
  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.9) return 'bg-green-500/20 text-green-400';
    if (confidence >= 0.7) return 'bg-yellow-500/20 text-yellow-400';
    return 'bg-red-500/20 text-red-400';
  };

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
            <GlassCardTitle>Preview da Planilha</GlassCardTitle>
            <Badge variant="outline" className="text-xs">
              {preview.file_type.toUpperCase()}
            </Badge>
          </div>
          <Badge className={getConfidenceBadge(confidence_score?.overall || 0)}>
            Match: {Math.round((stats.match_rate || 0) * 100)}%
          </Badge>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="space-y-6">
          {/* Stats Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-white/5 rounded-lg">
            <div>
              <p className="text-xs text-text-muted">Total de Linhas</p>
              <p className="text-lg font-medium text-text-primary">{preview.total_rows}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Linhas Encontradas</p>
              <p className="text-lg font-medium text-green-400">{stats.matched_count}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Nao Encontradas</p>
              <p className="text-lg font-medium text-yellow-400">{stats.unmatched_count}</p>
            </div>
            <div>
              <p className="text-xs text-text-muted">Quantidade Total</p>
              <p className="text-lg font-medium text-text-primary">{stats.total_quantity}</p>
            </div>
          </div>

          {/* Column Mappings */}
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
              <Columns className="w-4 h-4 text-blue-light" />
              Mapeamento de Colunas
            </h4>
            <div className="space-y-2">
              {column_mappings.map((mapping, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="flex items-center gap-3 p-2 bg-white/5 rounded-lg"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text-primary truncate">{mapping.file_column}</p>
                  </div>
                  <ArrowRight className="w-4 h-4 text-text-muted shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-blue-light truncate">{mapping.target_field}</p>
                  </div>
                  <Badge
                    className={`shrink-0 ${getConfidenceBadge(mapping.confidence)}`}
                  >
                    {Math.round(mapping.confidence * 100)}%
                  </Badge>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Unmapped Columns Warning */}
          {preview.unmapped_columns.length > 0 && (
            <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <HelpCircle className="w-4 h-4 text-yellow-400" />
                <p className="text-xs font-medium text-yellow-400">Colunas Nao Mapeadas</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {preview.unmapped_columns.map((col, i) => (
                  <Badge key={i} variant="outline" className="text-xs text-yellow-400 border-yellow-500/30">
                    {col}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Sample Data Preview */}
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
              <Table className="w-4 h-4 text-emerald-400" />
              Amostra de Dados ({stats.preview_rows_shown} linhas)
            </h4>
            <ScrollArea className="h-48">
              <div className="space-y-2">
                {matched_rows.slice(0, 5).map((row, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="flex items-center gap-3 p-3 bg-white/5 rounded-lg"
                  >
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
                      row.pn_match ? 'bg-green-500/20' : 'bg-yellow-500/20'
                    }`}>
                      {row.pn_match ? (
                        <Check className="w-3 h-3 text-green-400" />
                      ) : (
                        <HelpCircle className="w-3 h-3 text-yellow-400" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary truncate">
                        {row.mapped_data?.part_number || row.mapped_data?.description || `Linha ${row.row_number}`}
                      </p>
                      <p className="text-xs text-text-muted">
                        Qtd: {row.mapped_data?.quantity || '-'} | Match: {row.match_method || '-'}
                      </p>
                    </div>
                    <Badge className={getConfidenceBadge(row.match_confidence)}>
                      {Math.round(row.match_confidence * 100)}%
                    </Badge>
                  </motion.div>
                ))}

                {/* Unmatched rows preview */}
                {unmatched_rows.slice(0, 3).map((row, index) => (
                  <motion.div
                    key={`unmatched-${index}`}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: (matched_rows.length + index) * 0.05 }}
                    className="flex items-center gap-3 p-3 bg-red-500/5 border border-red-500/20 rounded-lg"
                  >
                    <div className="w-6 h-6 rounded-full flex items-center justify-center bg-red-500/20">
                      <X className="w-3 h-3 text-red-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-red-400 truncate">
                        {row.mapped_data?.description || `Linha ${row.row_number}`}
                      </p>
                      {row.validation_errors.length > 0 && (
                        <p className="text-xs text-red-400/70">
                          {row.validation_errors[0]}
                        </p>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* HIL Warning */}
          {needsHIL && (
            <div className="flex items-start gap-3 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-yellow-400">
                  Revisao Necessaria
                </p>
                <p className="text-xs text-yellow-400/80 mt-1">
                  Algumas linhas nao foram mapeadas automaticamente. Revise os dados antes de confirmar.
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
              className="flex-1 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-500/80 hover:to-green-500/80 text-white"
              disabled={isConfirming || stats.matched_count === 0}
            >
              {isConfirming ? (
                <>Importando...</>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Importar {stats.matched_count} Itens
                </>
              )}
            </Button>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
