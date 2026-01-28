'use client';

// =============================================================================
// Reversa Kanban Board - Carrier AgentCore Integration
// =============================================================================
// Visual tracking board for reverse logistics (reversa) workflow.
// 5-column Kanban: pendente → postado → em_transito → ocorrencia → entregue
// Drag-drop updates status via updateReversaStatus() API.
// =============================================================================

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  GlassCard,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowLeft,
  Package,
  RefreshCw,
  Filter,
  CheckCircle2,
  Clock,
  Truck,
  AlertTriangle,
  MapPin,
  Calendar,
  Hash,
  User,
  Barcode,
} from 'lucide-react';
import {
  getReversas,
  updateReversaStatus,
} from '@/services/carrierAgentcore';
import type {
  SGAReversa,
  SGAReversaStatus,
} from '@/lib/ativos/types';
import { formatDate } from '@/lib/utils';

// =============================================================================
// Types
// =============================================================================

interface KanbanColumn {
  id: SGAReversaStatus;
  label: string;
  icon: typeof Clock;
  color: string;
  bgColor: string;
}

// =============================================================================
// Constants
// =============================================================================

const KANBAN_COLUMNS: KanbanColumn[] = [
  {
    id: 'pendente',
    label: 'Pendente',
    icon: Clock,
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-500/10 border-yellow-500/30',
  },
  {
    id: 'postado',
    label: 'Postado',
    icon: Package,
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/10 border-blue-500/30',
  },
  {
    id: 'em_transito',
    label: 'Em Trânsito',
    icon: Truck,
    color: 'text-purple-400',
    bgColor: 'bg-purple-500/10 border-purple-500/30',
  },
  {
    id: 'ocorrencia',
    label: 'Ocorrência',
    icon: AlertTriangle,
    color: 'text-orange-400',
    bgColor: 'bg-orange-500/10 border-orange-500/30',
  },
  {
    id: 'entregue',
    label: 'Entregue',
    icon: CheckCircle2,
    color: 'text-green-400',
    bgColor: 'bg-green-500/10 border-green-500/30',
  },
];

// =============================================================================
// Page Component
// =============================================================================

export default function ReversaKanbanPage() {
  const queryClient = useQueryClient();
  const [filterStatus, setFilterStatus] = useState<SGAReversaStatus | 'all'>('all');
  const [draggedItem, setDraggedItem] = useState<SGAReversa | null>(null);

  // Fetch all reversas
  const { data: reversasResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['reversas', filterStatus],
    queryFn: async () => {
      const filter = filterStatus === 'all' ? undefined : filterStatus;
      return getReversas(filter);
    },
    refetchInterval: 30000, // Auto-refresh every 30s
  });

  const reversas = reversasResponse?.data?.reversas || [];

  // Update status mutation
  const updateStatusMutation = useMutation({
    mutationFn: async ({
      reversa_id,
      new_status,
      tracking_code,
    }: {
      reversa_id: string;
      new_status: SGAReversaStatus;
      tracking_code?: string;
    }) => {
      return updateReversaStatus(reversa_id, new_status, tracking_code);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reversas'] });
    },
  });

  // Group reversas by status
  const reversasByStatus = KANBAN_COLUMNS.reduce(
    (acc, column) => {
      acc[column.id] = reversas.filter((r) => r.status === column.id);
      return acc;
    },
    {} as Record<SGAReversaStatus, SGAReversa[]>
  );

  // Drag handlers
  const handleDragStart = useCallback((reversa: SGAReversa) => {
    setDraggedItem(reversa);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggedItem(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDrop = useCallback(
    (targetStatus: SGAReversaStatus) => {
      if (!draggedItem || draggedItem.status === targetStatus) {
        setDraggedItem(null);
        return;
      }

      // Validate status transition
      const validTransitions: Record<SGAReversaStatus, SGAReversaStatus[]> = {
        pendente: ['postado', 'cancelado'],
        postado: ['em_transito', 'ocorrencia'],
        em_transito: ['entregue', 'ocorrencia'],
        ocorrencia: ['em_transito', 'entregue'],
        entregue: [], // Terminal state
        cancelado: [], // Terminal state
      };

      const allowed = validTransitions[draggedItem.status] || [];
      if (!allowed.includes(targetStatus)) {
        alert(
          `Transição inválida: ${draggedItem.status} → ${targetStatus}`
        );
        setDraggedItem(null);
        return;
      }

      // Update status
      updateStatusMutation.mutate({
        reversa_id: draggedItem.reversa_id,
        new_status: targetStatus,
        tracking_code: draggedItem.tracking_code,
      });

      setDraggedItem(null);
    },
    [draggedItem, updateStatusMutation]
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/reversa">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Logística Reversa
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-light" />
            Kanban de Reversas
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Acompanhamento visual do fluxo de retorno de equipamentos
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Filter Dropdown */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-text-muted" />
            <select
              className="px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
              value={filterStatus}
              onChange={(e) =>
                setFilterStatus(e.target.value as SGAReversaStatus | 'all')
              }
            >
              <option value="all">Todos os Status</option>
              {KANBAN_COLUMNS.map((col) => (
                <option key={col.id} value={col.id}>
                  {col.label}
                </option>
              ))}
            </select>
          </div>

          {/* Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw
              className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
            />
          </Button>
        </div>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {KANBAN_COLUMNS.map((col) => {
          const count = reversasByStatus[col.id]?.length || 0;
          const Icon = col.icon;
          return (
            <GlassCard key={col.id} padding="sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-text-muted">{col.label}</p>
                  <p className="text-2xl font-bold text-text-primary">
                    {count}
                  </p>
                </div>
                <Icon className={`w-8 h-8 ${col.color}`} />
              </div>
            </GlassCard>
          );
        })}
      </div>

      {/* Error State */}
      {error && (
        <GlassCard className="bg-red-500/10 border-red-500/30">
          <GlassCardContent>
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <p>Erro ao carregar reversas: {error.message}</p>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Kanban Board */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 overflow-x-auto">
        {KANBAN_COLUMNS.map((column) => {
          const Icon = column.icon;
          const items = reversasByStatus[column.id] || [];

          return (
            <div
              key={column.id}
              className="min-w-[280px]"
              onDragOver={handleDragOver}
              onDrop={() => handleDrop(column.id)}
            >
              {/* Column Header */}
              <div
                className={`p-3 rounded-t-lg border ${column.bgColor} flex items-center justify-between mb-2`}
              >
                <div className="flex items-center gap-2">
                  <Icon className={`w-4 h-4 ${column.color}`} />
                  <h3 className="font-medium text-text-primary text-sm">
                    {column.label}
                  </h3>
                </div>
                <Badge variant="secondary" className="text-xs">
                  {items.length}
                </Badge>
              </div>

              {/* Column Content */}
              <div className="space-y-2 min-h-[400px]">
                {items.length === 0 ? (
                  <div className="p-4 text-center text-text-muted text-sm border border-dashed border-border rounded-lg">
                    Nenhuma reversa
                  </div>
                ) : (
                  items.map((reversa) => (
                    <ReversaCard
                      key={reversa.reversa_id}
                      reversa={reversa}
                      onDragStart={() => handleDragStart(reversa)}
                      onDragEnd={handleDragEnd}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center p-8">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Reversa Card Component
// =============================================================================

interface ReversaCardProps {
  reversa: SGAReversa;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function ReversaCard({ reversa, onDragStart, onDragEnd }: ReversaCardProps) {
  const isDraggable = reversa.status !== 'entregue' && reversa.status !== 'cancelado';

  return (
    <GlassCard
      padding="sm"
      draggable={isDraggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`cursor-${isDraggable ? 'move' : 'default'} hover:shadow-lg transition-shadow`}
    >
      <GlassCardContent className="space-y-2">
        {/* Order Code */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <Hash className="w-3 h-3 text-blue-400" />
            <span className="text-sm font-mono font-medium text-blue-400">
              {reversa.order_code}
            </span>
          </div>
          {reversa.status === 'ocorrencia' && (
            <AlertTriangle className="w-4 h-4 text-orange-400" />
          )}
        </div>

        {/* Technician Name */}
        <div className="flex items-center gap-1">
          <User className="w-3 h-3 text-text-muted" />
          <span className="text-xs text-text-primary truncate">
            {reversa.technician_name || reversa.origin.name}
          </span>
        </div>

        {/* Equipment */}
        <div className="flex items-center gap-1">
          <Package className="w-3 h-3 text-text-muted" />
          <span className="text-xs text-text-secondary truncate">
            {reversa.equipment.description}
          </span>
        </div>

        {/* Authorization Code (E-Ticket) */}
        <div className="p-2 bg-white/5 rounded border border-border">
          <p className="text-xs text-text-muted mb-1">E-Ticket</p>
          <div className="flex items-center gap-1">
            <Barcode className="w-3 h-3 text-green-400" />
            <span className="text-xs font-mono text-green-400">
              {reversa.authorization_code}
            </span>
          </div>
        </div>

        {/* Tracking Code */}
        {reversa.tracking_code && (
          <div className="p-2 bg-white/5 rounded border border-border">
            <p className="text-xs text-text-muted mb-1">Rastreio</p>
            <div className="flex items-center gap-1">
              <MapPin className="w-3 h-3 text-purple-400" />
              <span className="text-xs font-mono text-purple-400">
                {reversa.tracking_code}
              </span>
            </div>
          </div>
        )}

        {/* Created At */}
        <div className="flex items-center gap-1 text-xs text-text-muted">
          <Calendar className="w-3 h-3" />
          <span>{formatDate(reversa.created_at)}</span>
        </div>

        {/* Destination */}
        <div className="flex items-center gap-1 text-xs text-text-muted">
          <MapPin className="w-3 h-3" />
          <span>{reversa.destination_depot}</span>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
