'use client';

// =============================================================================
// TextPreview - AI Text Import Preview Component
// =============================================================================
// Displays items extracted from unstructured text via Gemini AI.
// Always requires human-in-the-loop review due to low confidence.
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
  FileType,
  Package,
  CheckCircle2,
  AlertTriangle,
  Brain,
  Sparkles,
  MessageSquare,
  X,
  Edit3,
} from 'lucide-react';
import type { TextImportResult } from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Types
// =============================================================================

interface TextPreviewProps {
  preview: TextImportResult;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  isConfirming?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function TextPreview({
  preview,
  onConfirm,
  onCancel,
  isConfirming = false,
}: TextPreviewProps) {
  const { items, confidence, notes, raw_text_preview } = preview;

  // Text imports ALWAYS require HIL
  const needsHIL = true;

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <FileType className="w-4 h-4 text-yellow-400" />
            <GlassCardTitle>Interpretacao AI</GlassCardTitle>
            <Badge className="bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-400 border-none">
              <Brain className="w-3 h-3 mr-1" />
              Gemini AI
            </Badge>
          </div>
          <Badge className="bg-yellow-500/20 text-yellow-400">
            Confianca: {Math.round(confidence * 100)}%
          </Badge>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="space-y-6">
          {/* AI Processing Notice */}
          <div className="flex items-start gap-3 p-4 bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-purple-400 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-purple-400">
                Processamento por Inteligencia Artificial
              </p>
              <p className="text-xs text-purple-400/80 mt-1">
                Os dados abaixo foram extraidos de texto nao estruturado usando Gemini AI.
                Revisao manual e <strong>obrigatoria</strong> antes de confirmar.
              </p>
            </div>
          </div>

          {/* AI Notes */}
          {notes && (
            <div className="p-3 bg-white/5 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <MessageSquare className="w-4 h-4 text-text-muted" />
                <p className="text-xs font-medium text-text-muted">Notas da AI</p>
              </div>
              <p className="text-sm text-text-secondary">{notes}</p>
            </div>
          )}

          {/* Source Text Preview */}
          {raw_text_preview && (
            <div className="p-3 bg-white/5 rounded-lg border border-border">
              <div className="flex items-center gap-2 mb-2">
                <FileType className="w-4 h-4 text-text-muted" />
                <p className="text-xs font-medium text-text-muted">Texto Original</p>
              </div>
              <pre className="text-xs text-text-muted font-mono whitespace-pre-wrap max-h-24 overflow-y-auto">
                {raw_text_preview.substring(0, 500)}
                {raw_text_preview.length > 500 && '...'}
              </pre>
            </div>
          )}

          {/* Extracted Items */}
          <div>
            <h4 className="text-sm font-medium text-text-primary mb-3 flex items-center gap-2">
              <Package className="w-4 h-4 text-yellow-400" />
              Itens Extraidos ({items.length})
            </h4>

            {items.length === 0 ? (
              <div className="text-center py-8 bg-white/5 rounded-lg">
                <AlertTriangle className="w-8 h-8 text-yellow-400 mx-auto mb-2" />
                <p className="text-sm text-text-muted">Nenhum item identificado</p>
                <p className="text-xs text-text-muted mt-1">
                  A AI nao conseguiu extrair itens de inventario do texto fornecido.
                </p>
              </div>
            ) : (
              <ScrollArea className="h-48">
                <div className="space-y-2">
                  {items.map((item, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="group relative p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-yellow-500/20 flex items-center justify-center shrink-0">
                          <Package className="w-4 h-4 text-yellow-400" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-text-primary">
                            {item.description || 'Sem descricao'}
                          </p>
                          <div className="flex items-center gap-2 mt-1">
                            {item.part_number && (
                              <Badge variant="outline" className="text-xs">
                                PN: {item.part_number}
                              </Badge>
                            )}
                            {item.serial && (
                              <Badge variant="outline" className="text-xs">
                                SN: {item.serial}
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-sm font-medium text-text-primary">
                            Qtd: {item.quantity} {item.unit || 'un'}
                          </p>
                          {item.confidence && (
                            <p className="text-xs text-text-muted">
                              {Math.round(item.confidence * 100)}% conf.
                            </p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Edit3 className="w-3 h-3" />
                        </Button>
                      </div>

                      {/* Raw text source */}
                      {item.raw_text && (
                        <p className="text-xs text-text-muted mt-2 pl-11 truncate">
                          Fonte: "{item.raw_text}"
                        </p>
                      )}
                    </motion.div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>

          {/* HIL Warning - Always shown for text imports */}
          <div className="flex items-start gap-3 p-4 bg-orange-500/20 border border-orange-500/30 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-orange-400">
                Revisao Obrigatoria
              </p>
              <p className="text-xs text-orange-400/80 mt-1">
                Importacoes de texto sempre requerem revisao humana.
                Verifique cada item antes de confirmar para garantir a precisao dos dados.
              </p>
            </div>
          </div>

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
              className="flex-1 bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-500/80 hover:to-orange-500/80 text-white"
              disabled={isConfirming || items.length === 0}
            >
              {isConfirming ? (
                <>Processando...</>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Revisar e Confirmar
                </>
              )}
            </Button>
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
