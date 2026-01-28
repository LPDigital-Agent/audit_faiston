'use client';

// =============================================================================
// SAP Reconciliation Page - SGA Inventory Module
// =============================================================================
// Manual SAP reconciliation workflow:
// 1. User exports CSV from SAP with part numbers, locations, quantities
// 2. Upload CSV here for comparison with SGA inventory
// 3. System identifies deltas: FALTA_SGA (missing in SGA), SOBRA_SGA (extra in SGA)
// 4. User applies actions: CREATE_ADJUSTMENT, IGNORE, INVESTIGATE
// =============================================================================

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowRightLeft,
  ArrowLeft,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Search,
  Settings2,
  Eye,
  MinusCircle,
  PlusCircle,
} from 'lucide-react';
import { reconcileSAPExport, applyReconciliationAction } from '@/services/sgaAgentcore';
import type {
  SGASAPExportItem,
  SGAReconciliationDelta,
  SGAReconciliationAction,
  SGAReconcileSAPResponse,
} from '@/lib/ativos/types';

// =============================================================================
// CSV Parser Helper
// =============================================================================

function parseCSV(csvText: string): SGASAPExportItem[] {
  const lines = csvText.trim().split('\n');
  if (lines.length < 2) return [];

  // Parse header row
  const headers = lines[0].split(/[,;]/).map(h => h.trim().toLowerCase());

  // Map column indices
  const pnIndex = headers.findIndex(h =>
    ['part_number', 'pn', 'codigo', 'material', 'matnr'].includes(h)
  );
  const locIndex = headers.findIndex(h =>
    ['location', 'loc', 'deposito', 'lgort', 'local'].includes(h)
  );
  const qtyIndex = headers.findIndex(h =>
    ['quantity', 'qty', 'quantidade', 'menge', 'qtd'].includes(h)
  );
  const serialIndex = headers.findIndex(h =>
    ['serial', 'sn', 'serie', 'sernr'].includes(h)
  );
  const descIndex = headers.findIndex(h =>
    ['description', 'desc', 'descricao', 'maktx', 'nome'].includes(h)
  );

  if (pnIndex < 0 || locIndex < 0 || qtyIndex < 0) {
    throw new Error('CSV deve conter colunas: part_number, location, quantity');
  }

  // Parse data rows
  const items: SGASAPExportItem[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(/[,;]/).map(c => c.trim());
    if (cols.length < 3) continue;

    items.push({
      part_number: cols[pnIndex],
      location: cols[locIndex],
      quantity: parseFloat(cols[qtyIndex]) || 0,
      serial: serialIndex >= 0 ? cols[serialIndex] : undefined,
      description: descIndex >= 0 ? cols[descIndex] : undefined,
    });
  }

  return items;
}

// =============================================================================
// Page Component
// =============================================================================

export default function SAPReconciliationPage() {
  // State
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvData, setCsvData] = useState<SGASAPExportItem[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [reconciliationResult, setReconciliationResult] = useState<SGAReconcileSAPResponse | null>(null);
  const [actionResults, setActionResults] = useState<Record<string, string>>({});

  // Reconciliation mutation
  const reconcileMutation = useMutation({
    mutationFn: async (data: SGASAPExportItem[]) => {
      const result = await reconcileSAPExport({ sap_data: data });
      return result.data;
    },
    onSuccess: (data) => {
      setReconciliationResult(data);
      setActionResults({});
    },
  });

  // Action mutation
  const actionMutation = useMutation({
    mutationFn: async ({ deltaId, action, reason }: { deltaId: string; action: SGAReconciliationAction; reason?: string }) => {
      const result = await applyReconciliationAction({ delta_id: deltaId, action, reason });
      return result.data;
    },
    onSuccess: (data) => {
      setActionResults(prev => ({
        ...prev,
        [data.delta_id]: data.message,
      }));
    },
  });

  // File handler
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCsvFile(file);
    setParseError(null);
    setReconciliationResult(null);
    setActionResults({});

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = parseCSV(text);
        setCsvData(parsed);
      } catch (err) {
        setParseError((err as Error).message);
        setCsvData([]);
      }
    };
    reader.readAsText(file);
  }, []);

  // Start reconciliation
  const handleReconcile = () => {
    if (csvData.length === 0) return;
    reconcileMutation.mutate(csvData);
  };

  // Apply action to delta
  const handleAction = (deltaId: string, action: SGAReconciliationAction) => {
    actionMutation.mutate({ deltaId, action });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Estoque
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-blue-400" />
            Reconciliação SAP
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Compare estoque SAP com SGA e identifique divergências
          </p>
        </div>

        {/* Link to Analytics */}
        <Button variant="outline" size="sm" asChild>
          <Link href="/ferramentas/ativos/estoque/analytics">
            <Settings2 className="w-4 h-4 mr-2" />
            Ver Métricas
          </Link>
        </Button>
      </div>

      {/* Step 1: Upload CSV */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle>1. Upload do Relatório SAP</GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="space-y-4">
            <p className="text-sm text-text-muted">
              Exporte um relatório de estoque do SAP em formato CSV contendo as colunas:
              <span className="font-mono text-xs ml-2">part_number, location, quantity</span>
            </p>

            {/* File Upload Zone */}
            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-blue-500/50 transition-colors">
              <input
                type="file"
                accept=".csv,.txt"
                onChange={handleFileChange}
                className="hidden"
                id="csv-upload"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <FileSpreadsheet className="w-12 h-12 text-text-muted mx-auto mb-4" />
                <p className="text-sm text-text-primary mb-2">
                  {csvFile ? csvFile.name : 'Clique para selecionar arquivo CSV'}
                </p>
                <p className="text-xs text-text-muted">
                  Suporta .csv e .txt com delimitador vírgula ou ponto-e-vírgula
                </p>
              </label>
            </div>

            {/* Parse Error */}
            {parseError && (
              <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <p className="text-sm text-red-400">{parseError}</p>
              </div>
            )}

            {/* Preview */}
            {csvData.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="text-green-400 border-green-400">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    {csvData.length} itens carregados
                  </Badge>
                  <Button
                    onClick={handleReconcile}
                    disabled={reconcileMutation.isPending}
                  >
                    {reconcileMutation.isPending ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Comparando...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4 mr-2" />
                        Iniciar Reconciliação
                      </>
                    )}
                  </Button>
                </div>

                {/* Preview Table */}
                <div className="max-h-48 overflow-auto border border-border rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-white/5 sticky top-0">
                      <tr>
                        <th className="text-left px-3 py-2 text-text-muted">Part Number</th>
                        <th className="text-left px-3 py-2 text-text-muted">Location</th>
                        <th className="text-right px-3 py-2 text-text-muted">Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {csvData.slice(0, 10).map((item, idx) => (
                        <tr key={idx} className="border-t border-border">
                          <td className="px-3 py-2 text-text-primary">{item.part_number}</td>
                          <td className="px-3 py-2 text-text-primary">{item.location}</td>
                          <td className="px-3 py-2 text-text-primary text-right">{item.quantity}</td>
                        </tr>
                      ))}
                      {csvData.length > 10 && (
                        <tr className="border-t border-border">
                          <td colSpan={3} className="px-3 py-2 text-text-muted text-center">
                            ... e mais {csvData.length - 10} itens
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </GlassCardContent>
      </GlassCard>

      {/* Reconciliation Error */}
      {reconcileMutation.error && (
        <div className="flex items-center gap-2 p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <p className="text-sm text-red-400">
            Erro na reconciliação: {(reconcileMutation.error as Error).message}
          </p>
        </div>
      )}

      {/* Step 2: Results */}
      {reconciliationResult && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between">
              <GlassCardTitle>2. Resultado da Reconciliação</GlassCardTitle>
              <Badge variant="outline">
                ID: {reconciliationResult.reconciliation_id}
              </Badge>
            </div>
          </GlassCardHeader>
          <GlassCardContent>
            {/* Summary */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
              <div className="p-4 bg-white/5 rounded-lg text-center">
                <p className="text-2xl font-bold text-text-primary">
                  {reconciliationResult.total_sap_items}
                </p>
                <p className="text-xs text-text-muted">Itens SAP</p>
              </div>
              <div className="p-4 bg-white/5 rounded-lg text-center">
                <p className="text-2xl font-bold text-green-400">
                  {reconciliationResult.match_rate.toFixed(1)}%
                </p>
                <p className="text-xs text-text-muted">Taxa de Match</p>
              </div>
              <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-center">
                <p className="text-2xl font-bold text-red-400">
                  {reconciliationResult.summary.falta_sga}
                </p>
                <p className="text-xs text-text-muted">Falta no SGA</p>
              </div>
              <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-center">
                <p className="text-2xl font-bold text-yellow-400">
                  {reconciliationResult.summary.sobra_sga}
                </p>
                <p className="text-xs text-text-muted">Sobra no SGA</p>
              </div>
            </div>

            {/* Delta List */}
            {reconciliationResult.deltas.length > 0 ? (
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-text-primary">
                  Divergências ({reconciliationResult.deltas.length})
                </h3>
                <div className="space-y-2">
                  {reconciliationResult.deltas.map((delta) => (
                    <DeltaRow
                      key={delta.id}
                      delta={delta}
                      onAction={handleAction}
                      actionResult={actionResults[delta.id]}
                      isLoading={actionMutation.isPending}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center p-8 bg-green-500/10 border border-green-500/30 rounded-lg">
                <CheckCircle2 className="w-6 h-6 text-green-400 mr-2" />
                <p className="text-green-400 font-medium">
                  Nenhuma divergência encontrada! SAP e SGA estão sincronizados.
                </p>
              </div>
            )}
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Instructions */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle>Instruções</GlassCardTitle>
        </GlassCardHeader>
        <GlassCardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm text-text-muted">
            <div>
              <h4 className="font-medium text-text-primary mb-2">Exportar do SAP</h4>
              <ol className="list-decimal list-inside space-y-1">
                <li>Acesse SAP via Skyone Autosky</li>
                <li>Navegue até Estoque → Relatórios</li>
                <li>Selecione &quot;Posição de Estoque&quot;</li>
                <li>Exporte como CSV</li>
              </ol>
            </div>
            <div>
              <h4 className="font-medium text-text-primary mb-2">Tipos de Divergência</h4>
              <ul className="space-y-1">
                <li><MinusCircle className="w-3 h-3 inline text-red-400 mr-1" /> <strong>FALTA_SGA</strong>: Item existe no SAP mas não no SGA</li>
                <li><PlusCircle className="w-3 h-3 inline text-yellow-400 mr-1" /> <strong>SOBRA_SGA</strong>: Item existe no SGA mas não no SAP</li>
              </ul>
            </div>
            <div>
              <h4 className="font-medium text-text-primary mb-2">Ações Disponíveis</h4>
              <ul className="space-y-1">
                <li><Settings2 className="w-3 h-3 inline text-blue-400 mr-1" /> <strong>Criar Ajuste</strong>: Gera movimento de ajuste</li>
                <li><XCircle className="w-3 h-3 inline text-gray-400 mr-1" /> <strong>Ignorar</strong>: Marca como divergência conhecida</li>
                <li><Eye className="w-3 h-3 inline text-yellow-400 mr-1" /> <strong>Investigar</strong>: Cria tarefa HIL</li>
              </ul>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}

// =============================================================================
// Delta Row Component
// =============================================================================

interface DeltaRowProps {
  delta: SGAReconciliationDelta;
  onAction: (deltaId: string, action: SGAReconciliationAction) => void;
  actionResult?: string;
  isLoading: boolean;
}

function DeltaRow({ delta, onAction, actionResult, isLoading }: DeltaRowProps) {
  const isFalta = delta.delta_type === 'FALTA_SGA';

  return (
    <div className={`p-4 border rounded-lg ${
      actionResult
        ? 'bg-green-500/5 border-green-500/30'
        : isFalta
          ? 'bg-red-500/5 border-red-500/30'
          : 'bg-yellow-500/5 border-yellow-500/30'
    }`}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {/* Delta Info */}
        <div className="flex items-center gap-3">
          {isFalta ? (
            <MinusCircle className="w-5 h-5 text-red-400" />
          ) : (
            <PlusCircle className="w-5 h-5 text-yellow-400" />
          )}
          <div>
            <p className="text-sm font-medium text-text-primary">
              {delta.part_number}
            </p>
            <p className="text-xs text-text-muted">
              {delta.location} • SAP: {delta.sap_quantity} • SGA: {delta.sga_quantity} • Δ {delta.delta}
            </p>
          </div>
          <Badge
            variant="outline"
            className={isFalta ? 'text-red-400 border-red-400' : 'text-yellow-400 border-yellow-400'}
          >
            {delta.delta_type}
          </Badge>
        </div>

        {/* Actions or Result */}
        {actionResult ? (
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-sm">{actionResult}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onAction(delta.id, 'CREATE_ADJUSTMENT')}
              disabled={isLoading}
            >
              <Settings2 className="w-3 h-3 mr-1" />
              Ajustar
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAction(delta.id, 'IGNORE')}
              disabled={isLoading}
            >
              <XCircle className="w-3 h-3 mr-1" />
              Ignorar
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAction(delta.id, 'INVESTIGATE')}
              disabled={isLoading}
            >
              <Eye className="w-3 h-3 mr-1" />
              Investigar
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
