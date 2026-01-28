'use client';

// =============================================================================
// Carrier CSV Upload Page - V2 LLM-Assisted Schema Detection
// =============================================================================
// Upload carrier pricing CSV with automatic schema detection via Strands agent.
// The agent (Gemini) reasons about CSV structure and produces CarrierSchemaV2.
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
  Check,
} from 'lucide-react';
import {
  previewCarrierCsv,
  ingestCarrierCsv,
  type PreviewCarrierCsvResponse,
  type CarrierSchemaV2,
} from '@/services/carrierAgentcore';

// =============================================================================
// Types
// =============================================================================

interface IngestionResult {
  success: boolean;
  carrier_id: string;
  version: number;
  routes_created: number;
  message: string;
  errors?: Array<{ row?: number; error: string }>;
}

// Role display labels (pt-BR)
const ROLE_LABELS: Record<string, string> = {
  state: 'UF',
  zone: 'Zona',
  region: 'Regiao',
  city: 'Cidade',
  weight_tier: 'Faixa de Peso',
  flat_price: 'Preco Fixo',
  excess_rate: 'Excedente',
  delivery_days: 'Prazo',
  notes: 'Obs.',
  ignored: 'Ignorado',
  surcharge_advalorem: 'Ad Valorem',
  surcharge_gris: 'GRIS',
  surcharge_fixed: 'Taxa Fixa',
  min_price: 'Preco Min.',
  cep_range_start: 'CEP Inicio',
  cep_range_end: 'CEP Fim',
  service_level: 'Servico',
  pickup_days: 'Coleta',
};

const PRICING_MODEL_LABELS: Record<string, string> = {
  weight_tiers: 'Faixas de Peso',
  flat_plus_excess: 'Preco Fixo + Excedente',
  per_kg: 'Preco por Kg',
  custom: 'Personalizado',
};

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
  const [preview, setPreview] = useState<PreviewCarrierCsvResponse | null>(null);

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
      return result.data as PreviewCarrierCsvResponse;
    },
    onSuccess: (data) => {
      setPreview(data);
    },
  });

  // Ingest mutation — requires v2_schema from preview
  const ingestMutation = useMutation({
    mutationFn: async () => {
      if (!fileContent || !carrierName || !preview?.v2_schema) {
        throw new Error('Schema V2 nao detectado — execute a deteccao primeiro');
      }
      const result = await ingestCarrierCsv({
        csv_content: fileContent,
        carrier_name: carrierName,
        schema_override: preview.v2_schema,
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
    ingestMutation.mutate();
  };

  // V2 schema helpers
  const v2Schema = preview?.v2_schema;
  const weightTierColumns = v2Schema?.columns?.filter(c => c.role === 'weight_tier') || [];
  const routingColumns = v2Schema?.columns?.filter(c =>
    ['state', 'zone', 'region', 'city', 'cep_range_start', 'cep_range_end'].includes(c.role)
  ) || [];
  const pricingColumns = v2Schema?.columns?.filter(c =>
    ['weight_tier', 'flat_price', 'excess_rate', 'min_price', 'surcharge_advalorem', 'surcharge_gris', 'surcharge_fixed'].includes(c.role)
  ) || [];
  const infoColumns = v2Schema?.columns?.filter(c =>
    ['delivery_days', 'pickup_days', 'notes'].includes(c.role)
  ) || [];

  const hasValidSchema = !!v2Schema && !!v2Schema.columns?.length;
  const validation = preview?.validation;

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
            Upload de CSV com deteccao automatica de formato (V2)
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

        {/* Schema Preview — V2 */}
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between">
              <GlassCardTitle>2. Schema Detectado (V2)</GlassCardTitle>
              {v2Schema && (
                <Badge className="text-blue-400">
                  <Sparkles className="w-3 h-3 mr-1" />
                  {v2Schema.schema_version}
                </Badge>
              )}
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            {!preview ? (
              <div className="text-center py-12">
                <Eye className="w-10 h-10 text-text-muted mx-auto mb-3" />
                <p className="text-sm text-text-muted">
                  Faca upload de um CSV e clique em &quot;Detectar Formato&quot;
                  <br />
                  para visualizar a estrutura detectada pela IA
                </p>
              </div>
            ) : preview.error ? (
              <div className="p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
                <p className="text-sm text-red-400">{preview.error}</p>
              </div>
            ) : !hasValidSchema ? (
              <div className="p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                <p className="text-sm text-yellow-400">
                  O agente nao conseguiu produzir um schema V2. Tente novamente.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Validation Status */}
                {validation && !validation.valid && (
                  <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <p className="text-sm font-medium text-red-400 mb-2">
                      Erros de validacao:
                    </p>
                    <ul className="text-xs text-red-400 list-disc list-inside">
                      {validation.errors?.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {validation?.warnings && validation.warnings.length > 0 && (
                  <div className="p-3 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                    <p className="text-sm font-medium text-yellow-400 mb-2">
                      Avisos:
                    </p>
                    <ul className="text-xs text-yellow-400 list-disc list-inside">
                      {validation.warnings.map((warn, i) => (
                        <li key={i}>{warn}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Pricing Model */}
                <div>
                  <p className="text-sm font-medium text-text-primary mb-2">
                    Modelo de Precificacao
                  </p>
                  <Badge variant="outline" className="text-purple-400 border-purple-400/30">
                    {PRICING_MODEL_LABELS[v2Schema!.pricing_model.type] || v2Schema!.pricing_model.type}
                  </Badge>
                </div>

                {/* Routing Columns */}
                {routingColumns.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Colunas de Roteamento
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {routingColumns.map((col, i) => (
                        <div key={i} className="p-2 bg-white/5 rounded">
                          <span className="text-text-muted">{ROLE_LABELS[col.role] || col.role}:</span>{' '}
                          <span className="text-text-primary">{col.column_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Weight Tiers / Pricing Columns */}
                {weightTierColumns.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Faixas de Peso ({weightTierColumns.length})
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {weightTierColumns.map((col, i) => (
                        <Badge key={i} variant="outline">
                          {(col.metadata?.weight_kg as number) || '?'}kg — {col.column_name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Non-weight pricing columns */}
                {pricingColumns.filter(c => c.role !== 'weight_tier').length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Colunas de Preco
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {pricingColumns.filter(c => c.role !== 'weight_tier').map((col, i) => (
                        <div key={i} className="p-2 bg-white/5 rounded">
                          <span className="text-text-muted">{ROLE_LABELS[col.role] || col.role}:</span>{' '}
                          <span className="text-text-primary">{col.column_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Info Columns */}
                {infoColumns.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Informacionais
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {infoColumns.map((col, i) => (
                        <div key={i} className="p-2 bg-white/5 rounded">
                          <span className="text-text-muted">{ROLE_LABELS[col.role] || col.role}:</span>{' '}
                          <span className="text-text-primary">{col.column_name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Notes from agent */}
                {v2Schema!.notes && v2Schema!.notes.length > 0 && (
                  <div>
                    <p className="text-sm font-medium text-text-primary mb-2">
                      Observacoes do Agente
                    </p>
                    <ul className="text-xs text-text-muted list-disc list-inside">
                      {v2Schema!.notes.map((note, i) => (
                        <li key={i}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Stats */}
                <div className="flex items-center gap-4 text-sm text-text-muted">
                  <div className="flex items-center gap-1">
                    <Table className="w-4 h-4" />
                    {preview.total_rows} linhas
                  </div>
                  <div className="flex items-center gap-1">
                    {preview.headers?.length || 0} colunas
                  </div>
                  <div className="flex items-center gap-1">
                    {v2Schema!.columns.length} mapeadas
                  </div>
                </div>

                {/* Confirm Button — only if schema exists (validation is optional since agent produces it) */}
                {hasValidSchema && (!validation || validation.valid) && (
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
                <p className="font-medium text-text-primary">Deteccao AI (V2)</p>
                <p className="text-sm text-text-muted">
                  Agente Gemini analisa e classifica cada coluna com roles semanticos
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
