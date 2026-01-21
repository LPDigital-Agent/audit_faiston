'use client';

// =============================================================================
// Carrier CSV Upload Page - LLM-Assisted Schema Detection
// =============================================================================
// Upload carrier pricing CSV with automatic schema detection.
// Uses Gemini to analyze CSV structure and generate mappings.
// =============================================================================

import { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
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
  Truck,
  ArrowLeft,
  Upload,
  FileSpreadsheet,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Eye,
  Sparkles,
  Table,
  ArrowRight,
  Check,
  Edit,
} from 'lucide-react';
import { previewCarrierCsv, ingestCarrierCsv } from '@/services/carrierAgentcore';

// =============================================================================
// Types
// =============================================================================

interface WeightTier {
  column_name: string;
  weight_kg: number;
}

interface SchemaPreview {
  success: boolean;
  schema: {
    carrier_name: string;
    carrier_id: string;
    region_column?: string;
    state_column?: string;
    zone_column?: string;
    delivery_days_column?: string;
    price_tiers: WeightTier[];
    excess_column?: string;
    price_format: string;
    detected_columns: string[];
    unmapped_columns: string[];
    detection_confidence: number;
    notes: string[];
  };
  validation: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  };
  sample_routes: Array<{
    uf: string;
    zone: string;
    [key: string]: string | number;
  }>;
  total_rows: number;
  headers: string[];
  detection_confidence: number;
  error?: string;
}

interface IngestionResult {
  success: boolean;
  carrier_id: string;
  version: number;
  routes_created: number;
  message: string;
  errors?: Array<{ row?: number; error: string }>;
}

// =============================================================================
// Page Component
// =============================================================================

export default function CarrierUploadPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const existingCarrierId = searchParams.get('carrier');

  // Form state
  const [carrierName, setCarrierName] = useState(existingCarrierId || '');
  const [file, setFile] = useState<File | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);

  // Preview state
  const [preview, setPreview] = useState<SchemaPreview | null>(null);
  const [schemaConfirmed, setSchemaConfirmed] = useState(false);

  // File drop handling
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setFileContent(ev.target?.result as string);
      };
      reader.readAsText(droppedFile);
      setPreview(null);
      setSchemaConfirmed(false);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      const reader = new FileReader();
      reader.onload = (ev) => {
        setFileContent(ev.target?.result as string);
      };
      reader.readAsText(selectedFile);
      setPreview(null);
      setSchemaConfirmed(false);
    }
  };

  // Preview mutation (schema detection)
  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!fileContent || !carrierName) {
        throw new Error('Arquivo e nome da transportadora sao obrigatorios');
      }
      const result = await previewCarrierCsv({
        csv_content: fileContent,
        carrier_name: carrierName,
      });
      return result.data as SchemaPreview;
    },
    onSuccess: (data) => {
      setPreview(data);
    },
  });

  // Ingest mutation
  const ingestMutation = useMutation({
    mutationFn: async () => {
      if (!fileContent || !carrierName || !preview?.schema) {
        throw new Error('Schema nao confirmado');
      }
      const result = await ingestCarrierCsv({
        csv_content: fileContent,
        carrier_name: carrierName,
        schema_override: schemaConfirmed ? preview.schema : undefined,
      });
      return result.data as IngestionResult;
    },
  });

  // Redirect after successful ingestion
  useEffect(() => {
    if (ingestMutation.isSuccess && ingestMutation.data?.success) {
      const timer = setTimeout(() => {
        router.push('/ferramentas/ativos/transportadoras');
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [ingestMutation.isSuccess, ingestMutation.data, router]);

  const handlePreview = () => {
    previewMutation.mutate();
  };

  const handleConfirmAndIngest = () => {
    setSchemaConfirmed(true);
    ingestMutation.mutate();
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-400';
    if (confidence >= 0.7) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/transportadoras">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Transportadoras
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Upload className="w-5 h-5 text-blue-400" />
            {existingCarrierId ? 'Atualizar Tabela de Precos' : 'Nova Transportadora'}
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Upload de CSV com deteccao automatica de formato
          </p>
        </div>
      </div>

      {/* Success Message */}
      {ingestMutation.isSuccess && ingestMutation.data?.success && (
        <GlassCard>
          <GlassCardContent className="py-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-green-400" />
              </div>
              <div>
                <h3 className="text-lg font-medium text-green-400">
                  Importacao concluida com sucesso!
                </h3>
                <p className="text-sm text-text-muted mt-1">
                  {ingestMutation.data.routes_created} rotas criadas para{' '}
                  {ingestMutation.data.carrier_id} (v{ingestMutation.data.version})
                </p>
                <p className="text-xs text-text-muted mt-2">
                  Redirecionando...
                </p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Form */}
        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle>1. Upload do Arquivo</GlassCardTitle>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-4">
              {/* Carrier Name */}
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Nome da Transportadora *
                </label>
                <Input
                  placeholder="Ex: TRB, Jadlog, Braspress"
                  value={carrierName}
                  onChange={(e) => setCarrierName(e.target.value.toUpperCase())}
                  className="bg-white/5 border-border"
                  disabled={!!existingCarrierId}
                />
              </div>

              {/* File Drop Zone */}
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Arquivo CSV *
                </label>
                <div
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  className={`
                    border-2 border-dashed rounded-lg p-8 text-center transition-colors
                    ${file ? 'border-green-500/50 bg-green-500/5' : 'border-border hover:border-blue-500/50'}
                  `}
                >
                  {file ? (
                    <div className="flex items-center justify-center gap-3">
                      <FileSpreadsheet className="w-8 h-8 text-green-400" />
                      <div className="text-left">
                        <p className="font-medium text-text-primary">{file.name}</p>
                        <p className="text-sm text-text-muted">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setFile(null);
                          setFileContent(null);
                          setPreview(null);
                        }}
                      >
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-10 h-10 text-text-muted mx-auto mb-3" />
                      <p className="text-sm text-text-primary mb-1">
                        Arraste o arquivo CSV aqui
                      </p>
                      <p className="text-xs text-text-muted mb-3">
                        ou clique para selecionar
                      </p>
                      <input
                        type="file"
                        accept=".csv"
                        onChange={handleFileSelect}
                        className="hidden"
                        id="csv-upload"
                      />
                      <Button variant="outline" size="sm" asChild>
                        <label htmlFor="csv-upload" className="cursor-pointer">
                          Selecionar arquivo
                        </label>
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {/* Preview Button */}
              <Button
                className="w-full"
                disabled={!file || !carrierName || previewMutation.isPending}
                onClick={handlePreview}
              >
                {previewMutation.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Analisando com IA...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Detectar Formato
                  </>
                )}
              </Button>

              {/* Preview Error */}
              {previewMutation.error && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <p className="text-sm text-red-400">
                    {previewMutation.error.message}
                  </p>
                </div>
              )}
            </div>
          </GlassCardContent>
        </GlassCard>

        {/* Schema Preview */}
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between">
              <GlassCardTitle>2. Formato Detectado</GlassCardTitle>
              {preview && (
                <Badge className={`${getConfidenceColor(preview.detection_confidence)}`}>
                  <Sparkles className="w-3 h-3 mr-1" />
                  {(preview.detection_confidence * 100).toFixed(0)}% confianca
                </Badge>
              )}
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            {!preview ? (
              <div className="text-center py-12">
                <Eye className="w-10 h-10 text-text-muted mx-auto mb-3" />
                <p className="text-sm text-text-muted">
                  Faca upload de um CSV e clique em "Detectar Formato"
                  <br />
                  para visualizar a estrutura detectada pela IA
                </p>
              </div>
            ) : preview.error ? (
              <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
                <p className="text-sm text-red-400">{preview.error}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Validation Status */}
                {preview.validation && !preview.validation.valid && (
                  <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <p className="text-sm font-medium text-red-400 mb-2">
                      Erros de validacao:
                    </p>
                    <ul className="text-xs text-red-400 list-disc list-inside">
                      {preview.validation?.errors?.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {preview.validation?.warnings && preview.validation.warnings.length > 0 && (
                  <div className="p-3 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                    <p className="text-sm font-medium text-yellow-400 mb-2">
                      Avisos:
                    </p>
                    <ul className="text-xs text-yellow-400 list-disc list-inside">
                      {preview.validation.warnings.map((warn, i) => (
                        <li key={i}>{warn}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Column Mappings */}
                <div>
                  <p className="text-sm font-medium text-text-primary mb-2">
                    Mapeamento de Colunas
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="p-2 bg-white/5 rounded">
                      <span className="text-text-muted">UF:</span>{' '}
                      <span className="text-text-primary">
                        {preview.schema.state_column || '-'}
                      </span>
                    </div>
                    <div className="p-2 bg-white/5 rounded">
                      <span className="text-text-muted">Zona:</span>{' '}
                      <span className="text-text-primary">
                        {preview.schema.zone_column || '-'}
                      </span>
                    </div>
                    <div className="p-2 bg-white/5 rounded">
                      <span className="text-text-muted">Prazo:</span>{' '}
                      <span className="text-text-primary">
                        {preview.schema.delivery_days_column || '-'}
                      </span>
                    </div>
                    <div className="p-2 bg-white/5 rounded">
                      <span className="text-text-muted">Excedente:</span>{' '}
                      <span className="text-text-primary">
                        {preview.schema.excess_column || '-'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Price Tiers */}
                <div>
                  <p className="text-sm font-medium text-text-primary mb-2">
                    Faixas de Peso ({preview.schema.price_tiers.length})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {preview.schema.price_tiers.map((tier, i) => (
                      <Badge key={i} variant="outline">
                        {tier.weight_kg}kg
                      </Badge>
                    ))}
                  </div>
                </div>

                {/* Sample Routes */}
                {preview.sample_routes.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Amostra de Rotas
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 px-2 text-text-muted">UF</th>
                            <th className="text-left py-2 px-2 text-text-muted">Zona</th>
                            <th className="text-right py-2 px-2 text-text-muted">
                              Preco {preview.schema.price_tiers[0]?.weight_kg}kg
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {preview.sample_routes.slice(0, 5).map((route, i) => (
                            <tr key={i} className="border-b border-border/50">
                              <td className="py-2 px-2 text-text-primary">{route.uf}</td>
                              <td className="py-2 px-2 text-text-primary">{route.zone}</td>
                              <td className="py-2 px-2 text-right text-green-400">
                                R$ {Object.values(route).find(v => typeof v === 'number')?.toFixed(2) || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-text-muted">
                  <div className="flex items-center gap-1">
                    <Table className="w-4 h-4" />
                    {preview.total_rows} linhas
                  </div>
                  <div className="flex items-center gap-1">
                    {preview.headers.length} colunas
                  </div>
                </div>

                {/* Confirm Button */}
                {preview.validation?.valid && (
                  <Button
                    className="w-full"
                    disabled={ingestMutation.isPending}
                    onClick={handleConfirmAndIngest}
                  >
                    {ingestMutation.isPending ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Importando...
                      </>
                    ) : (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Confirmar e Importar
                      </>
                    )}
                  </Button>
                )}

                {/* Ingest Error */}
                {ingestMutation.error && (
                  <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
                    <p className="text-sm text-red-400">
                      {ingestMutation.error.message}
                    </p>
                  </div>
                )}
              </div>
            )}
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* How It Works */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle>Como funciona</GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-blue-400">1</span>
              </div>
              <div>
                <p className="font-medium text-text-primary">Upload CSV</p>
                <p className="text-sm text-text-muted">
                  Faca upload da tabela de precos no formato CSV
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-purple-400">2</span>
              </div>
              <div>
                <p className="font-medium text-text-primary">Deteccao AI</p>
                <p className="text-sm text-text-muted">
                  Gemini analisa e detecta colunas de preco, UF, zona, prazo
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-bold text-green-400">3</span>
              </div>
              <div>
                <p className="font-medium text-text-primary">Ativo</p>
                <p className="text-sm text-text-muted">
                  Precos disponiveis nas cotacoes imediatamente
                </p>
              </div>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
