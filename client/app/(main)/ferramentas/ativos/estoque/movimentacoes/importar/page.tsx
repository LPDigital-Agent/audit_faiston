'use client';

// =============================================================================
// Importar Page - SGA Inventory Module
// =============================================================================
// Bulk import of inventory data from CSV/Excel files.
// Supports auto-column detection and AI-powered PN matching.
// =============================================================================

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  FileUp,
  ArrowLeft,
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Package,
  MapPin,
  Briefcase,
  X,
  Download,
  Table,
  ArrowRight,
  Zap,
} from 'lucide-react';
import { useBulkImport, useLocations, useProjects } from '@/hooks/ativos';
import type { ImportPreviewRow } from '@/lib/ativos/types';

// =============================================================================
// Confidence Badge
// =============================================================================

function ConfidenceBadge({ confidence }: { confidence: number }) {
  if (confidence >= 0.9) {
    return (
      <Badge className="bg-green-500/20 text-green-400">
        {Math.round(confidence * 100)}%
      </Badge>
    );
  }
  if (confidence >= 0.7) {
    return (
      <Badge className="bg-yellow-500/20 text-yellow-400">
        {Math.round(confidence * 100)}%
      </Badge>
    );
  }
  if (confidence > 0) {
    return (
      <Badge className="bg-orange-500/20 text-orange-400">
        {Math.round(confidence * 100)}%
      </Badge>
    );
  }
  return (
    <Badge className="bg-red-500/20 text-red-400">
      Sem match
    </Badge>
  );
}

// =============================================================================
// Page Component
// =============================================================================

export default function ImportarPage() {
  // Hooks
  const {
    isLoading,
    isPreviewing,
    isExecuting,
    error,
    preview,
    columnMappings,
    matchedRows,
    unmatchedRows,
    pnOverrides,
    uploadAndPreview,
    executeImportAction,
    updateColumnMapping,
    setPNOverride,
    removePNOverride,
    clearImport,
    filename,
  } = useBulkImport();

  const { locations } = useLocations();
  const { projects } = useProjects();

  // Local state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [selectedLocation, setSelectedLocation] = useState<string>('');
  const [importResult, setImportResult] = useState<{
    success: boolean;
    message: string;
    created: number;
    failed: number;
  } | null>(null);
  const [step, setStep] = useState<'upload' | 'preview' | 'result'>('upload');

  // File drop handler
  const handleFileDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) {
        const ext = file.name.toLowerCase();
        if (ext.endsWith('.csv') || ext.endsWith('.xlsx')) {
          setSelectedFile(file);
        } else {
          alert('Formato nao suportado. Use CSV ou XLSX.');
        }
      }
    },
    []
  );

  // File select handler
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setSelectedFile(file);
      }
    },
    []
  );

  // Preview handler
  const handlePreview = useCallback(async () => {
    if (!selectedFile) return;

    const result = await uploadAndPreview(
      selectedFile,
      selectedProject || undefined,
      selectedLocation || undefined
    );

    if (result?.success) {
      setStep('preview');
    }
  }, [selectedFile, selectedProject, selectedLocation, uploadAndPreview]);

  // Execute import handler
  const handleExecuteImport = useCallback(async () => {
    const result = await executeImportAction();

    if (result) {
      setImportResult({
        success: result.success,
        message: result.message,
        created: result.created_count,
        failed: result.failed_count + result.skipped_count,
      });
      setStep('result');
    }
  }, [executeImportAction]);

  // Reset handler
  const handleReset = useCallback(() => {
    clearImport();
    setSelectedFile(null);
    setSelectedProject('');
    setSelectedLocation('');
    setImportResult(null);
    setStep('upload');
  }, [clearImport]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/ferramentas/ativos/estoque/movimentacoes">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">Importar em Massa</h1>
          <p className="text-gray-400">
            Importe itens de inventario via CSV ou Excel
          </p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-4">
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded-full ${
            step === 'upload'
              ? 'bg-[var(--faiston-blue-mid)]/20 text-[var(--faiston-blue-light)]'
              : 'bg-gray-800 text-gray-400'
          }`}
        >
          <Upload className="h-4 w-4" />
          <span>1. Upload</span>
        </div>
        <ArrowRight className="h-4 w-4 text-gray-600" />
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded-full ${
            step === 'preview'
              ? 'bg-[var(--faiston-blue-mid)]/20 text-[var(--faiston-blue-light)]'
              : 'bg-gray-800 text-gray-400'
          }`}
        >
          <Table className="h-4 w-4" />
          <span>2. Preview</span>
        </div>
        <ArrowRight className="h-4 w-4 text-gray-600" />
        <div
          className={`flex items-center gap-2 px-4 py-2 rounded-full ${
            step === 'result'
              ? 'bg-green-500/20 text-green-400'
              : 'bg-gray-800 text-gray-400'
          }`}
        >
          <CheckCircle2 className="h-4 w-4" />
          <span>3. Resultado</span>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-3"
        >
          <AlertTriangle className="h-5 w-5 text-red-400" />
          <span className="text-red-300">{error}</span>
        </motion.div>
      )}

      {/* Step: Upload */}
      <AnimatePresence mode="wait">
        {step === 'upload' && (
          <motion.div
            key="upload"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Drop zone */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>
                  <FileSpreadsheet className="h-5 w-5 text-[var(--faiston-blue-light)]" />
                  Selecionar Arquivo
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent>
                <div
                  className={`
                    relative border-2 border-dashed rounded-xl p-12
                    flex flex-col items-center justify-center gap-4
                    transition-colors cursor-pointer
                    ${
                      selectedFile
                        ? 'border-green-500/50 bg-green-500/5'
                        : 'border-gray-600 hover:border-[var(--faiston-blue-mid)] bg-gray-800/30'
                    }
                  `}
                  onDrop={handleFileDrop}
                  onDragOver={(e) => e.preventDefault()}
                  onClick={() =>
                    document.getElementById('file-input')?.click()
                  }
                >
                  <input
                    id="file-input"
                    type="file"
                    accept=".csv,.xlsx"
                    onChange={handleFileSelect}
                    className="hidden"
                  />

                  {selectedFile ? (
                    <>
                      <FileSpreadsheet className="h-12 w-12 text-green-400" />
                      <div className="text-center">
                        <p className="text-white font-medium">
                          {selectedFile.name}
                        </p>
                        <p className="text-gray-400 text-sm">
                          {(selectedFile.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedFile(null);
                        }}
                      >
                        <X className="h-4 w-4 mr-1" />
                        Remover
                      </Button>
                    </>
                  ) : (
                    <>
                      <FileUp className="h-12 w-12 text-gray-400" />
                      <div className="text-center">
                        <p className="text-white">
                          Arraste o arquivo aqui ou clique para selecionar
                        </p>
                        <p className="text-gray-400 text-sm mt-1">
                          Suporta CSV e Excel (.xlsx)
                        </p>
                      </div>
                    </>
                  )}
                </div>

                {/* Template download */}
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-gray-400">
                  <Download className="h-4 w-4" />
                  <span>Baixar template de exemplo</span>
                </div>
              </GlassCardContent>
            </GlassCard>

            {/* Options */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>
                  <Briefcase className="h-5 w-5 text-[var(--faiston-magenta-mid)]" />
                  Opcoes de Importacao
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent className="space-y-4">
                {/* Project selection */}
                <div>
                  <label className="block text-sm text-gray-400 mb-2">
                    <Briefcase className="h-4 w-4 inline mr-1" />
                    Projeto (opcional)
                  </label>
                  <select
                    value={selectedProject}
                    onChange={(e) => setSelectedProject(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">Usar coluna do arquivo</option>
                    {projects?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} - {p.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Se selecionado, todos os itens serao atribuidos a este
                    projeto
                  </p>
                </div>

                {/* Location selection */}
                <div>
                  <label className="block text-sm text-gray-400 mb-2">
                    <MapPin className="h-4 w-4 inline mr-1" />
                    Local de Destino (opcional)
                  </label>
                  <select
                    value={selectedLocation}
                    onChange={(e) => setSelectedLocation(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">Usar coluna do arquivo</option>
                    {locations?.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.code} - {l.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    Se selecionado, todos os itens serao direcionados a este
                    local
                  </p>
                </div>

                {/* Expected columns */}
                <div className="p-4 bg-gray-800/50 rounded-lg">
                  <h4 className="text-sm font-medium text-gray-300 mb-2">
                    Colunas Esperadas
                  </h4>
                  <ul className="text-xs text-gray-400 space-y-1">
                    <li>
                      <strong>part_number</strong> - Codigo do material
                      (obrigatorio)
                    </li>
                    <li>
                      <strong>quantity</strong> - Quantidade (obrigatorio)
                    </li>
                    <li>
                      <strong>description</strong> - Descricao do item
                    </li>
                    <li>
                      <strong>serial</strong> - Numero de serie
                    </li>
                    <li>
                      <strong>location</strong> - Local/deposito
                    </li>
                    <li>
                      <strong>project</strong> - ID do projeto
                    </li>
                  </ul>
                </div>

                {/* Process button */}
                <Button
                  className="w-full bg-[var(--faiston-blue-mid)] hover:bg-[var(--faiston-blue-dark)]"
                  disabled={!selectedFile || isPreviewing}
                  onClick={handlePreview}
                >
                  {isPreviewing ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Processando...
                    </>
                  ) : (
                    <>
                      <Zap className="h-4 w-4 mr-2" />
                      Processar Arquivo
                    </>
                  )}
                </Button>
              </GlassCardContent>
            </GlassCard>
          </motion.div>
        )}

        {/* Step: Preview */}
        {step === 'preview' && preview && (
          <motion.div
            key="preview"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="space-y-6"
          >
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <GlassCard>
                <GlassCardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-white">
                    {preview.total_rows}
                  </p>
                  <p className="text-sm text-gray-400">Total de linhas</p>
                </GlassCardContent>
              </GlassCard>
              <GlassCard>
                <GlassCardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-green-400">
                    {preview.stats.matched_count}
                  </p>
                  <p className="text-sm text-gray-400">PNs encontrados</p>
                </GlassCardContent>
              </GlassCard>
              <GlassCard>
                <GlassCardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-orange-400">
                    {preview.stats.unmatched_count}
                  </p>
                  <p className="text-sm text-gray-400">Sem match</p>
                </GlassCardContent>
              </GlassCard>
              <GlassCard>
                <GlassCardContent className="p-4 text-center">
                  <p className="text-3xl font-bold text-[var(--faiston-blue-light)]">
                    {preview.stats.match_rate}%
                  </p>
                  <p className="text-sm text-gray-400">Taxa de match</p>
                </GlassCardContent>
              </GlassCard>
            </div>

            {/* Column mappings */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>
                  <Table className="h-5 w-5 text-[var(--faiston-blue-light)]" />
                  Mapeamento de Colunas
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {columnMappings.map((mapping, index) => (
                    <div
                      key={mapping.file_column}
                      className="p-3 bg-gray-800/50 rounded-lg"
                    >
                      <p className="text-sm text-gray-400 mb-1">
                        {mapping.file_column}
                      </p>
                      <div className="flex items-center gap-2">
                        <ArrowRight className="h-3 w-3 text-gray-600" />
                        <span className="text-white font-medium">
                          {mapping.target_field}
                        </span>
                        <ConfidenceBadge confidence={mapping.confidence} />
                      </div>
                    </div>
                  ))}
                </div>

                {preview.unmapped_columns.length > 0 && (
                  <div className="mt-4 p-3 bg-yellow-500/10 rounded-lg">
                    <p className="text-sm text-yellow-400">
                      Colunas ignoradas: {preview.unmapped_columns.join(', ')}
                    </p>
                  </div>
                )}
              </GlassCardContent>
            </GlassCard>

            {/* Preview rows */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>
                  <Package className="h-5 w-5 text-green-400" />
                  Preview dos Itens ({preview.stats.preview_rows_shown} de{' '}
                  {preview.total_rows})
                </GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left p-2 text-gray-400">Linha</th>
                        <th className="text-left p-2 text-gray-400">
                          Part Number
                        </th>
                        <th className="text-left p-2 text-gray-400">
                          Descricao
                        </th>
                        <th className="text-left p-2 text-gray-400">Qtd</th>
                        <th className="text-left p-2 text-gray-400">
                          Match
                        </th>
                        <th className="text-left p-2 text-gray-400">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...matchedRows, ...unmatchedRows]
                        .slice(0, 10)
                        .map((row) => (
                          <tr
                            key={row.row_number}
                            className="border-b border-gray-800"
                          >
                            <td className="p-2 text-gray-400">
                              {row.row_number}
                            </td>
                            <td className="p-2 text-white">
                              {row.mapped_data.part_number || '-'}
                            </td>
                            <td className="p-2 text-gray-300 max-w-[200px] truncate">
                              {row.mapped_data.description || '-'}
                            </td>
                            <td className="p-2 text-white">
                              {row.mapped_data.quantity || '-'}
                            </td>
                            <td className="p-2">
                              {row.pn_match ? (
                                <span className="text-green-400">
                                  {row.pn_match.part_number}
                                </span>
                              ) : (
                                <span className="text-orange-400">-</span>
                              )}
                            </td>
                            <td className="p-2">
                              <ConfidenceBadge
                                confidence={row.match_confidence}
                              />
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </GlassCardContent>
            </GlassCard>

            {/* Actions */}
            <div className="flex items-center justify-between">
              <Button variant="outline" onClick={handleReset}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Voltar
              </Button>

              <div className="flex items-center gap-3">
                {preview.requires_review && (
                  <Badge className="bg-yellow-500/20 text-yellow-400">
                    <AlertTriangle className="h-3 w-3 mr-1" />
                    Revisao recomendada
                  </Badge>
                )}

                <Button
                  className="bg-green-600 hover:bg-green-700"
                  disabled={isExecuting}
                  onClick={handleExecuteImport}
                >
                  {isExecuting ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Importando...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Confirmar Importacao
                    </>
                  )}
                </Button>
              </div>
            </div>
          </motion.div>
        )}

        {/* Step: Result */}
        {step === 'result' && importResult && (
          <motion.div
            key="result"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="max-w-xl mx-auto"
          >
            <GlassCard>
              <GlassCardContent className="p-8 text-center">
                {importResult.success ? (
                  <>
                    <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                      <CheckCircle2 className="h-8 w-8 text-green-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2">
                      Importacao Concluida!
                    </h2>
                    <p className="text-gray-400 mb-6">{importResult.message}</p>

                    <div className="grid grid-cols-2 gap-4 mb-6">
                      <div className="p-4 bg-green-500/10 rounded-lg">
                        <p className="text-3xl font-bold text-green-400">
                          {importResult.created}
                        </p>
                        <p className="text-sm text-gray-400">
                          Itens importados
                        </p>
                      </div>
                      {importResult.failed > 0 && (
                        <div className="p-4 bg-red-500/10 rounded-lg">
                          <p className="text-3xl font-bold text-red-400">
                            {importResult.failed}
                          </p>
                          <p className="text-sm text-gray-400">Falhas</p>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
                      <AlertTriangle className="h-8 w-8 text-red-400" />
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2">
                      Erro na Importacao
                    </h2>
                    <p className="text-red-400 mb-6">{importResult.message}</p>
                  </>
                )}

                <div className="flex items-center justify-center gap-3">
                  <Button variant="outline" onClick={handleReset}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Nova Importacao
                  </Button>
                  <Link href="/ferramentas/ativos/estoque">
                    <Button className="bg-[var(--faiston-blue-mid)] hover:bg-[var(--faiston-blue-dark)]">
                      Ir para Estoque
                    </Button>
                  </Link>
                </div>
              </GlassCardContent>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
