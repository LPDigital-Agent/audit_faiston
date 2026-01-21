'use client';

// =============================================================================
// Asset Detail Content - SGA Inventory Module
// =============================================================================
// Single asset view with timeline, metadata, and quick actions.
// Client component for dynamic rendering.
// =============================================================================

import Link from 'next/link';
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
  Package,
  ArrowLeft,
  MapPin,
  Calendar,
  FileText,
  History,
  ArrowRightLeft,
  RefreshCw,
  Edit,
} from 'lucide-react';
import { useAssetDetail } from '@/hooks/ativos';
import {
  SGA_STATUS_LABELS,
  SGA_STATUS_COLORS,
  SGA_MOVEMENT_LABELS,
} from '@/lib/ativos/constants';

// =============================================================================
// Component
// =============================================================================

interface AssetDetailContentProps {
  id: string;
}

export function AssetDetailContent({ id }: AssetDetailContentProps) {
  const { asset, timeline, isLoading, isError, error, refetch } = useAssetDetail({ serialNumber: id });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
      </div>
    );
  }

  if (isError || !asset) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
        <Package className="w-16 h-16 text-text-muted mb-4" />
        <h2 className="text-lg font-semibold text-text-primary mb-2">
          Ativo nao encontrado
        </h2>
        <p className="text-sm text-text-muted mb-4">
          {typeof error === 'string' ? error : 'O ativo solicitado nao existe ou foi removido.'}
        </p>
        <Button asChild>
          <Link href="/ferramentas/ativos/estoque/lista">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Voltar a lista
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/lista">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Voltar
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            {asset.serial_number || asset.id}
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Part Number: {asset.part_number_id}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Atualizar
          </Button>
          <Button>
            <Edit className="w-4 h-4 mr-2" />
            Editar
          </Button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Asset Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Package className="w-4 h-4 text-blue-light" />
                <GlassCardTitle>Informacoes do Ativo</GlassCardTitle>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-text-muted mb-1">Status</p>
                  <Badge className={SGA_STATUS_COLORS[asset.status] || 'bg-gray-500/20'}>
                    {SGA_STATUS_LABELS[asset.status] || asset.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-1">Projeto</p>
                  <p className="text-sm text-text-primary">
                    {asset.project_id || 'Nao vinculado'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-1">Serial Number</p>
                  <p className="text-sm text-text-primary font-mono">
                    {asset.serial_number || 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-1">Part Number</p>
                  <p className="text-sm text-text-primary">
                    {asset.part_number_id}
                  </p>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Location Info */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-green-400" />
                <GlassCardTitle>Localizacao</GlassCardTitle>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-text-muted mb-1">Local Atual</p>
                  <p className="text-sm text-text-primary">
                    {asset.location_id || 'Nao definido'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted mb-1">Projeto</p>
                  <p className="text-sm text-text-primary">
                    {asset.project_id || 'Nao vinculado'}
                  </p>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Timeline */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <History className="w-4 h-4 text-magenta-mid" />
                  <GlassCardTitle>Historico de Movimentacoes</GlassCardTitle>
                </div>
                <Badge variant="outline">{timeline.length} registros</Badge>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              {timeline.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <History className="w-12 h-12 text-text-muted mb-3" />
                  <p className="text-sm text-text-muted">
                    Nenhuma movimentacao registrada
                  </p>
                </div>
              ) : (
                <ScrollArea className="max-h-[400px]">
                  <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-4 top-2 bottom-2 w-px bg-border" />

                    <div className="space-y-4">
                      {timeline.map((movement, index) => (
                        <motion.div
                          key={movement.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: index * 0.05 }}
                          className="relative pl-10"
                        >
                          {/* Timeline dot */}
                          <div className="absolute left-2 top-2 w-4 h-4 rounded-full bg-blue-mid border-2 border-faiston-bg" />

                          <div className="p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors">
                            <div className="flex items-start justify-between">
                              <div>
                                <p className="text-sm font-medium text-text-primary">
                                  {SGA_MOVEMENT_LABELS[movement.type] || movement.type}
                                </p>
                                <p className="text-xs text-text-muted mt-1">
                                  {movement.source_location_id} → {movement.destination_location_id}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="text-xs text-text-muted">
                                  {new Date(movement.created_at).toLocaleDateString('pt-BR')}
                                </p>
                                <p className="text-xs text-text-muted">
                                  {new Date(movement.created_at).toLocaleTimeString('pt-BR', {
                                    hour: '2-digit',
                                    minute: '2-digit',
                                  })}
                                </p>
                              </div>
                            </div>
                            {movement.notes && (
                              <p className="text-xs text-text-muted mt-2 italic">
                                {movement.notes}
                              </p>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </ScrollArea>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Right Column - Quick Actions */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <ArrowRightLeft className="w-4 h-4 text-blue-light" />
                <GlassCardTitle>Acoes Rapidas</GlassCardTitle>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-2">
                <Button variant="outline" className="w-full justify-start" asChild>
                  <Link href={`/ferramentas/ativos/estoque/movimentacoes/transferencia?asset=${id}`}>
                    <ArrowRightLeft className="w-4 h-4 mr-2" />
                    Transferir
                  </Link>
                </Button>
                <Button variant="outline" className="w-full justify-start" asChild>
                  <Link href={`/ferramentas/ativos/estoque/movimentacoes/reserva?asset=${id}`}>
                    <Calendar className="w-4 h-4 mr-2" />
                    Reservar
                  </Link>
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  <FileText className="w-4 h-4 mr-2" />
                  Gerar Relatorio
                </Button>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Metadata */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-yellow-400" />
                <GlassCardTitle>Metadados</GlassCardTitle>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-text-muted">Criado em</p>
                  <p className="text-sm text-text-primary">
                    {new Date(asset.created_at).toLocaleDateString('pt-BR', {
                      day: '2-digit',
                      month: 'long',
                      year: 'numeric',
                    })}
                  </p>
                </div>
                {asset.updated_at && (
                  <div>
                    <p className="text-xs text-text-muted">Ultima atualizacao</p>
                    <p className="text-sm text-text-primary">
                      {new Date(asset.updated_at).toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: 'long',
                        year: 'numeric',
                      })}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-text-muted">ID do Ativo</p>
                  <p className="text-sm text-text-primary font-mono text-xs break-all">
                    {asset.id}
                  </p>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
