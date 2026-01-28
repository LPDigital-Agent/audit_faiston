'use client';

// =============================================================================
// SmartUploadZone - Universal File Upload Component
// =============================================================================
// Unified upload zone that accepts all file formats and auto-detects type.
// Replaces individual tabs (NF, Image, SAP Export) with intelligent routing.
//
// Philosophy: Observe -> Think -> Learn -> Act
// The component OBSERVES user interaction, THINKS about file type,
// LEARNS from detection, and ACTS by showing appropriate feedback.
// =============================================================================

import { useState, useCallback, createElement } from 'react';
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
  Upload,
  FileUp,
  FileCode,
  FileText,
  Image,
  Table,
  FileType,
  AlertTriangle,
  RefreshCw,
  Sparkles,
  Brain,
} from 'lucide-react';
import type {
  SmartFileType,
  SmartImportProgress,
} from '@/lib/ativos/smartImportTypes';
import { SMART_IMPORT_FORMATS, getFileTypeLabel, detectFileTypeFromFile } from '@/lib/ativos/smartImportTypes';

// BUG-027 FIX: Import DebugAnalysisPanel and EnrichedError type
import { DebugAnalysisPanel } from '@/components/shared/DebugAnalysisPanel';
import type { EnrichedError } from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Types
// =============================================================================

interface SmartUploadZoneProps {
  // Processing state
  isProcessing: boolean;
  progress: SmartImportProgress;
  // BUG-027 FIX: Changed from string | null to EnrichedError | null
  // to support DebugAnalysisPanel display with AI-powered error insights
  error: EnrichedError | null;
  detectedType: SmartFileType | null;

  // Actions - projectId and locationId are always null (determined by NEXO analysis)
  onFileSelect: (file: File, projectId: string | null, locationId: string | null) => Promise<void>;

  // BUG-027: Optional callback for debug analysis panel actions
  onDebugAction?: (action: 'retry' | 'fallback' | 'escalate' | 'abort') => void;
}

// =============================================================================
// Helpers
// =============================================================================

function getFileTypeIcon(fileType: SmartFileType | null) {
  if (!fileType) return Upload;

  const iconMap: Record<SmartFileType, typeof FileCode> = {
    xml: FileCode,
    pdf: FileText,
    image: Image,
    csv: Table,
    xlsx: Table,
    txt: FileType,
    unknown: FileType,
  };

  return iconMap[fileType] || FileType;
}

function getFileTypeColor(fileType: SmartFileType | null): string {
  if (!fileType) return 'text-text-muted';

  const colorMap: Record<SmartFileType, string> = {
    xml: 'text-green-400',
    pdf: 'text-red-400',
    image: 'text-blue-400',
    csv: 'text-emerald-400',
    xlsx: 'text-emerald-400',
    txt: 'text-yellow-400',
    unknown: 'text-gray-400',
  };

  return colorMap[fileType] || 'text-gray-400';
}

function getStageColor(stage: SmartImportProgress['stage']): string {
  switch (stage) {
    case 'detecting':
      return 'from-purple-500 to-blue-500';
    case 'uploading':
      return 'from-blue-500 to-cyan-500';
    case 'processing':
      return 'from-cyan-500 to-green-500';
    case 'complete':
      return 'from-green-500 to-green-400';
    case 'error':
      return 'from-red-500 to-red-400';
    default:
      return 'from-gray-500 to-gray-400';
  }
}

// =============================================================================
// Component
// =============================================================================

export function SmartUploadZone({
  isProcessing,
  progress,
  error,
  detectedType,
  onFileSelect,
  onDebugAction,
}: SmartUploadZoneProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewType, setPreviewType] = useState<SmartFileType | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // Handle file selection
  const handleFileChange = useCallback((file: File) => {
    setSelectedFile(file);
    const type = detectFileTypeFromFile(file);
    setPreviewType(type);
  }, []);

  // File input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileChange(file);
    }
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileChange(file);
    }
  };

  // Handle upload - Project and Location determined by NEXO analysis
  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      await onFileSelect(selectedFile, null, null);
    } catch {
      // Error handled by hook
    }
  };

  // Get icon component
  // Get the icon component for dynamic rendering
  const fileTypeIcon = getFileTypeIcon(previewType || detectedType);

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Sparkles className="w-4 h-4 text-magenta-mid" />
            <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          </div>
          <GlassCardTitle>Upload Inteligente</GlassCardTitle>
          <Badge className="bg-gradient-to-r from-blue-mid/20 to-magenta-mid/20 text-blue-light border-none">
            <Brain className="w-3 h-3 mr-1" />
            Auto-Detect
          </Badge>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="space-y-6">
          {/* Drop Zone */}
          <div
            className={`
              relative border-2 border-dashed rounded-lg p-8 text-center transition-all duration-300
              ${isDragOver
                ? 'border-magenta-mid bg-magenta-mid/10 scale-[1.02]'
                : 'border-border hover:border-blue-mid/50'
              }
              ${isProcessing ? 'opacity-50 pointer-events-none' : 'cursor-pointer'}
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <input
              type="file"
              accept={SMART_IMPORT_FORMATS.accept}
              onChange={handleInputChange}
              className="hidden"
              id="smart-upload"
              disabled={isProcessing}
            />
            <label htmlFor="smart-upload" className="cursor-pointer">
              {/* Animated Icon */}
              <motion.div
                className={`mx-auto mb-4 w-16 h-16 rounded-full flex items-center justify-center ${
                  selectedFile
                    ? 'bg-gradient-to-br from-blue-mid/20 to-magenta-mid/20'
                    : 'bg-white/5'
                }`}
                animate={{
                  scale: isDragOver ? 1.1 : 1,
                }}
                transition={{ duration: 0.2 }}
              >
                {createElement(fileTypeIcon, { className: `w-8 h-8 ${getFileTypeColor(previewType)}` })}
              </motion.div>

              {/* Text */}
              {selectedFile ? (
                <div>
                  <p className="text-sm font-medium text-text-primary mb-1">
                    {selectedFile.name}
                  </p>
                  <Badge className={`${getFileTypeColor(previewType)} bg-white/10 border-none`}>
                    {getFileTypeLabel(previewType || 'unknown')}
                  </Badge>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium text-text-primary mb-1">
                    Arraste seu arquivo aqui ou clique para selecionar
                  </p>
                  <p className="text-xs text-text-muted">
                    Formatos aceitos: XML, PDF, CSV, XLSX, JPG, PNG, TXT
                  </p>
                </div>
              )}
            </label>

            {/* Format Icons */}
            <div className="flex justify-center gap-3 mt-4 opacity-50">
              <FileCode className="w-4 h-4" aria-label="XML" />
              <FileText className="w-4 h-4" aria-label="PDF" />
              <Table className="w-4 h-4" aria-label="CSV/XLSX" />
              <Image className="w-4 h-4" aria-label="JPG/PNG" />
              <FileType className="w-4 h-4" aria-label="TXT" />
            </div>
          </div>

          {/* AI Processing Info */}
          <div className="flex items-center gap-3 p-3 bg-gradient-to-r from-blue-mid/10 to-magenta-mid/10 rounded-lg border border-blue-mid/20">
            <Brain className="w-5 h-5 text-magenta-mid" />
            <div className="text-xs text-text-muted">
              <p className="font-medium text-text-secondary mb-0.5">Processamento Inteligente</p>
              <p>
                O sistema detecta automaticamente o tipo de arquivo e roteia para o agente apropriado
                (IntakeAgent para NF, ImportAgent para planilhas e texto).
              </p>
            </div>
          </div>

          {/* Progress */}
          {isProcessing && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-blue-light" />
                  <span className="text-text-muted">{progress.message}</span>
                </div>
                <span className="text-text-primary font-medium">{progress.percent}%</span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  className={`h-full bg-gradient-to-r ${getStageColor(progress.stage)} rounded-full`}
                  initial={{ width: 0 }}
                  animate={{ width: `${progress.percent}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              {detectedType && (
                <p className="text-xs text-center text-text-muted">
                  Tipo detectado: <span className={getFileTypeColor(detectedType)}>{getFileTypeLabel(detectedType)}</span>
                </p>
              )}
            </div>
          )}

          {/* Error - BUG-027 FIX: Show DebugAnalysisPanel for enriched errors */}
          {error && (
            error.debug_analysis ? (
              // AI-powered error analysis with root causes and debugging steps
              <DebugAnalysisPanel
                analysis={error.debug_analysis}
                onAction={onDebugAction}
                defaultExpanded={true}
                className="mt-2"
              />
            ) : (
              // Fallback: Simple error display for non-enriched errors
              <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <p className="text-sm text-red-400">{error.message}</p>
              </div>
            )
          )}

          {/* Upload Button */}
          <div className="space-y-2">
            <Button
              className="w-full bg-gradient-to-r from-blue-mid to-magenta-mid hover:from-blue-mid/80 hover:to-magenta-mid/80 text-white"
              disabled={!selectedFile || isProcessing}
              onClick={handleUpload}
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Processando...
                </>
              ) : (
                <>
                  <FileUp className="w-4 h-4 mr-2" />
                  Processar Arquivo
                </>
              )}
            </Button>

            {/* Validation feedback - only file is required */}
            {!isProcessing && !selectedFile && (
              <p className="text-xs text-center text-amber-400">
                <AlertTriangle className="w-3 h-3 inline mr-1" />
                Selecione um arquivo para processar
              </p>
            )}
          </div>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
