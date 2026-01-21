'use client';

// =============================================================================
// Analytics Page - SGA Accuracy Dashboard
// =============================================================================
// KPI dashboard showing system accuracy metrics:
// - Extraction accuracy (NF parsing success rate)
// - Entry success rate (% without rejection)
// - Average HIL time (human-in-the-loop response time)
// - Divergence rate (inventory discrepancies)
// - PN matching breakdown by method
// - Movements summary by type
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  BarChart3,
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Clock,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Percent,
  Package,
  ArrowRightLeft,
  Settings2,
  Bookmark,
  FileQuestion,
  Users,
} from 'lucide-react';
import { getAccuracyMetrics } from '@/services/sgaAgentcore';
import type { SGAMetricsPeriod, SGAMetricValue } from '@/lib/ativos/types';

// =============================================================================
// Constants
// =============================================================================

const PERIOD_OPTIONS: { value: SGAMetricsPeriod; label: string }[] = [
  { value: '7d', label: 'Últimos 7 dias' },
  { value: '30d', label: 'Últimos 30 dias' },
  { value: '90d', label: 'Últimos 90 dias' },
  { value: 'ytd', label: 'Ano atual' },
];

// =============================================================================
// Components
// =============================================================================

interface MetricCardProps {
  title: string;
  metric: SGAMetricValue;
  icon: React.ReactNode;
  description?: string;
  colorClass?: string;
}

function MetricCard({ title, metric, icon, description, colorClass = 'text-blue-400' }: MetricCardProps) {
  const TrendIcon = metric.trend === 'up' ? TrendingUp : metric.trend === 'down' ? TrendingDown : Minus;
  const trendColor =
    metric.trend === 'up'
      ? (title.includes('Divergência') || title.includes('HIL') ? 'text-red-400' : 'text-green-400')
      : metric.trend === 'down'
        ? (title.includes('Divergência') || title.includes('HIL') ? 'text-green-400' : 'text-red-400')
        : 'text-gray-400';

  return (
    <GlassCard className="h-full">
      <GlassCardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className={`p-2 rounded-lg bg-white/5 ${colorClass}`}>
            {icon}
          </div>
          <div className={`flex items-center gap-1 text-xs ${trendColor}`}>
            <TrendIcon className="w-3 h-3" />
            <span>{Math.abs(metric.change).toFixed(1)}%</span>
          </div>
        </div>
        <p className="text-2xl font-bold text-text-primary mb-1">
          {metric.value.toFixed(1)}{metric.unit}
        </p>
        <p className="text-sm font-medium text-text-primary">{title}</p>
        {description && (
          <p className="text-xs text-text-muted mt-1">{description}</p>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}

// =============================================================================
// Page Component
// =============================================================================

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<SGAMetricsPeriod>('30d');

  // Fetch accuracy metrics
  const { data: metricsData, isLoading, error, refetch } = useQuery({
    queryKey: ['sga-accuracy-metrics', period],
    queryFn: async () => {
      const result = await getAccuracyMetrics({ period });
      return result.data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const metrics = metricsData?.metrics;

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
            <BarChart3 className="w-5 h-5 text-purple-400" />
            Dashboard de Acurácia
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Métricas de desempenho e confiabilidade do sistema SGA
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Period Selector */}
          <select
            className="px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
            value={period}
            onChange={(e) => setPeriod(e.target.value as SGAMetricsPeriod)}
          >
            {PERIOD_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <p className="text-sm text-red-400">Erro ao carregar métricas: {(error as Error).message}</p>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
        </div>
      )}

      {/* Metrics Content */}
      {metrics && (
        <>
          {/* Primary KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Acurácia de Extração"
              metric={metrics.extraction_accuracy}
              icon={<Target className="w-5 h-5" />}
              description="Taxa de NF processadas com sucesso"
              colorClass="text-green-400"
            />
            <MetricCard
              title="Taxa de Sucesso"
              metric={metrics.entry_success_rate}
              icon={<CheckCircle2 className="w-5 h-5" />}
              description="Entradas sem rejeição ou erro"
              colorClass="text-blue-400"
            />
            <MetricCard
              title="Tempo Médio HIL"
              metric={metrics.avg_hil_time}
              icon={<Clock className="w-5 h-5" />}
              description="Resposta para tarefas Human-in-Loop"
              colorClass="text-yellow-400"
            />
            <MetricCard
              title="Taxa de Divergência"
              metric={metrics.divergence_rate}
              icon={<AlertTriangle className="w-5 h-5" />}
              description="Discrepâncias identificadas"
              colorClass="text-red-400"
            />
          </div>

          {/* Secondary Analytics */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* PN Matching Breakdown */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>Matching de Part Numbers</GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent>
                <p className="text-sm text-text-muted mb-4">
                  Distribuição de métodos de identificação de itens
                </p>
                <div className="space-y-4">
                  <MatchingBar
                    label="Código do Fornecedor"
                    value={metrics.pn_match_by_method.supplier_code}
                    total={Object.values(metrics.pn_match_by_method).reduce((a, b) => a + b, 0)}
                    color="bg-green-500"
                    confidence="95%"
                  />
                  <MatchingBar
                    label="Descrição (AI)"
                    value={metrics.pn_match_by_method.description_ai}
                    total={Object.values(metrics.pn_match_by_method).reduce((a, b) => a + b, 0)}
                    color="bg-blue-500"
                    confidence="70-85%"
                  />
                  <MatchingBar
                    label="NCM (Categoria)"
                    value={metrics.pn_match_by_method.ncm}
                    total={Object.values(metrics.pn_match_by_method).reduce((a, b) => a + b, 0)}
                    color="bg-yellow-500"
                    confidence="60%"
                  />
                  <MatchingBar
                    label="Manual"
                    value={metrics.pn_match_by_method.manual}
                    total={Object.values(metrics.pn_match_by_method).reduce((a, b) => a + b, 0)}
                    color="bg-gray-500"
                    confidence="HIL"
                  />
                </div>
              </GlassCardContent>
            </GlassCard>

            {/* Movements Summary */}
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>Movimentações por Tipo</GlassCardTitle>
              </GlassCardHeader>
              <GlassCardContent>
                <p className="text-sm text-text-muted mb-4">
                  Resumo de operações no período selecionado
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <MovementStat
                    label="Entradas"
                    value={metrics.movements_summary.entrada}
                    icon={<Package className="w-4 h-4 text-green-400" />}
                  />
                  <MovementStat
                    label="Saídas"
                    value={metrics.movements_summary.saida}
                    icon={<Package className="w-4 h-4 text-red-400" />}
                  />
                  <MovementStat
                    label="Transferências"
                    value={metrics.movements_summary.transferencia}
                    icon={<ArrowRightLeft className="w-4 h-4 text-blue-400" />}
                  />
                  <MovementStat
                    label="Ajustes"
                    value={metrics.movements_summary.ajuste}
                    icon={<Settings2 className="w-4 h-4 text-yellow-400" />}
                  />
                  <MovementStat
                    label="Reservas"
                    value={metrics.movements_summary.reserva}
                    icon={<Bookmark className="w-4 h-4 text-purple-400" />}
                  />
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>

          {/* Pending Items */}
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle>Itens Pendentes</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <FileQuestion className="w-5 h-5 text-yellow-400" />
                    <span className="text-sm font-medium text-text-primary">Aguardando Projeto</span>
                  </div>
                  <p className="text-2xl font-bold text-yellow-400">
                    {metrics.pending_items.pending_project}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    Entradas sem ID de projeto atribuído
                  </p>
                </div>

                <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="w-5 h-5 text-blue-400" />
                    <span className="text-sm font-medium text-text-primary">Aguardando HIL</span>
                  </div>
                  <p className="text-2xl font-bold text-blue-400">
                    {metrics.pending_items.pending_hil}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    Tarefas de validação humana pendentes
                  </p>
                </div>

                <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <span className="text-sm font-medium text-text-primary">Reconciliação</span>
                  </div>
                  <p className="text-2xl font-bold text-red-400">
                    {metrics.pending_items.pending_reconciliation}
                  </p>
                  <p className="text-xs text-text-muted mt-1">
                    Divergências SAP aguardando resolução
                  </p>
                </div>
              </div>

              {/* Link to Reconciliation */}
              <div className="mt-4 pt-4 border-t border-border">
                <Link href="/ferramentas/ativos/estoque/reconciliacao/sap">
                  <Button variant="outline" size="sm">
                    <ArrowRightLeft className="w-4 h-4 mr-2" />
                    Ir para Reconciliação SAP
                  </Button>
                </Link>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Last Updated */}
          {metricsData?.generated_at && (
            <p className="text-xs text-text-muted text-right">
              Atualizado em: {new Date(metricsData.generated_at).toLocaleString('pt-BR')}
            </p>
          )}
        </>
      )}
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

interface MatchingBarProps {
  label: string;
  value: number;
  total: number;
  color: string;
  confidence: string;
}

function MatchingBar({ label, value, total, color, confidence }: MatchingBarProps) {
  const percentage = total > 0 ? (value / total) * 100 : 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-text-primary">{label}</span>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {confidence}
          </Badge>
          <span className="text-sm font-medium text-text-primary">{value}</span>
        </div>
      </div>
      <div className="h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

interface MovementStatProps {
  label: string;
  value: number;
  icon: React.ReactNode;
}

function MovementStat({ label, value, icon }: MovementStatProps) {
  return (
    <div className="p-3 bg-white/5 rounded-lg">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-text-muted">{label}</span>
      </div>
      <p className="text-lg font-bold text-text-primary">{value}</p>
    </div>
  );
}
