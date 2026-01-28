'use client';

// =============================================================================
// Inventario Page - SGA Inventory Module
// =============================================================================
// Inventory counting campaigns management.
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
  ClipboardCheck,
  Plus,
  RefreshCw,
  Calendar,
  MapPin,
  CheckCircle2,
  Clock,
  ChevronRight,
  Play,
} from 'lucide-react';
import { useInventoryCount } from '@/hooks/ativos';
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_STATUS_COLORS,
} from '@/lib/ativos/constants';

// =============================================================================
// Page Component
// =============================================================================

export default function InventarioPage() {
  const {
    campaigns,
    activeCampaign,
    campaignsLoading,
    refreshCampaigns,
  } = useInventoryCount();

  // Split campaigns by status
  const activeCampaigns = campaigns.filter(c => c.status === 'ACTIVE' || c.status === 'ANALYSIS');
  const completedCampaigns = campaigns.filter(c => c.status === 'COMPLETED' || c.status === 'CANCELLED');
  const plannedCampaigns = campaigns.filter(c => c.status === 'DRAFT');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Inventário
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Campanhas de contagem e reconciliação
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refreshCampaigns()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Atualizar
          </Button>
          <Button asChild>
            <Link href="/ferramentas/ativos/estoque/inventario/novo">
              <Plus className="w-4 h-4 mr-2" />
              Nova Campanha
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="w-5 h-5 text-blue-light" />
            <p className="text-2xl font-bold text-text-primary">
              {campaignsLoading ? '...' : campaigns.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Total de Campanhas</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Play className="w-5 h-5 text-green-400" />
            <p className="text-2xl font-bold text-green-400">
              {campaignsLoading ? '...' : activeCampaigns.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Em Andamento</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-yellow-400" />
            <p className="text-2xl font-bold text-yellow-400">
              {campaignsLoading ? '...' : plannedCampaigns.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Agendadas</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-magenta-mid" />
            <p className="text-2xl font-bold text-magenta-mid">
              {campaignsLoading ? '...' : completedCampaigns.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Concluídas</p>
        </GlassCard>
      </div>

      {/* Active Campaign Banner */}
      {activeCampaign && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <GlassCard className="border-green-500/30 bg-green-500/5">
            <GlassCardContent className="p-6">
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="p-3 rounded-lg bg-green-500/20">
                    <ClipboardCheck className="w-6 h-6 text-green-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-text-primary">
                      Campanha em Andamento
                    </h3>
                    <p className="text-sm text-text-muted mt-1">
                      {activeCampaign.name}
                    </p>
                    <div className="flex items-center gap-4 mt-2">
                      <span className="flex items-center gap-1 text-xs text-text-muted">
                        <MapPin className="w-3 h-3" />
                        {activeCampaign.location_ids?.length || 0} locais
                      </span>
                      <span className="flex items-center gap-1 text-xs text-text-muted">
                        <Clock className="w-3 h-3" />
                        Iniciada em {activeCampaign.started_at ? new Date(activeCampaign.started_at).toLocaleDateString('pt-BR') : 'Não iniciada'}
                      </span>
                    </div>
                  </div>
                </div>
                <Button asChild>
                  <Link href={`/ferramentas/ativos/estoque/inventario/${activeCampaign.id}`}>
                    Continuar Contagem
                  </Link>
                </Button>
              </div>
            </GlassCardContent>
          </GlassCard>
        </motion.div>
      )}

      {/* Campaigns List */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="w-4 h-4 text-blue-light" />
              <GlassCardTitle>Campanhas de Inventário</GlassCardTitle>
            </div>
            <Badge variant="outline">{campaigns.length} campanhas</Badge>
          </div>
        </GlassCardHeader>

        {/* Table Header */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wider">
          <div className="col-span-4">Campanha</div>
          <div className="col-span-2">Período</div>
          <div className="col-span-2">Locais</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2 text-right">Ações</div>
        </div>

        {campaignsLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
          </div>
        ) : campaigns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <ClipboardCheck className="w-12 h-12 text-text-muted mb-3" />
            <p className="text-sm text-text-muted mb-4">
              Nenhuma campanha de inventário criada
            </p>
            <Button asChild>
              <Link href="/ferramentas/ativos/estoque/inventario/novo">
                <Plus className="w-4 h-4 mr-2" />
                Criar Primeira Campanha
              </Link>
            </Button>
          </div>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="divide-y divide-border">
              {campaigns.map((campaign, index) => (
                <motion.div
                  key={campaign.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                >
                  <Link href={`/ferramentas/ativos/estoque/inventario/${campaign.id}`}>
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 px-4 py-4 hover:bg-white/5 transition-colors cursor-pointer items-center">
                      {/* Campaign Info */}
                      <div className="col-span-4 flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                          campaign.status === 'ACTIVE' ? 'bg-green-500/20' :
                          campaign.status === 'ANALYSIS' ? 'bg-yellow-500/20' :
                          'bg-blue-mid/20'
                        }`}>
                          <ClipboardCheck className={`w-5 h-5 ${
                            campaign.status === 'ACTIVE' ? 'text-green-400' :
                            campaign.status === 'ANALYSIS' ? 'text-yellow-400' :
                            'text-blue-light'
                          }`} />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-text-primary truncate">
                            {campaign.name}
                          </p>
                          <p className="text-xs text-text-muted truncate">
                            {campaign.description || 'Sem descrição'}
                          </p>
                        </div>
                      </div>

                      {/* Period */}
                      <div className="col-span-2">
                        <p className="text-sm text-text-primary">
                          {campaign.started_at ? new Date(campaign.started_at).toLocaleDateString('pt-BR') : 'Não iniciada'}
                        </p>
                        {campaign.completed_at && (
                          <p className="text-xs text-text-muted">
                            Concluída: {new Date(campaign.completed_at).toLocaleDateString('pt-BR')}
                          </p>
                        )}
                      </div>

                      {/* Locations */}
                      <div className="col-span-2 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-text-muted" />
                        <span className="text-sm text-text-muted">
                          {campaign.location_ids?.length || 0} locais
                        </span>
                      </div>

                      {/* Status */}
                      <div className="col-span-2">
                        <Badge className={CAMPAIGN_STATUS_COLORS[campaign.status] || 'bg-gray-500/20'}>
                          {CAMPAIGN_STATUS_LABELS[campaign.status] || campaign.status}
                        </Badge>
                      </div>

                      {/* Actions */}
                      <div className="col-span-2 flex items-center justify-end">
                        <ChevronRight className="w-4 h-4 text-text-muted" />
                      </div>
                    </div>
                  </Link>
                </motion.div>
              ))}
            </div>
          </ScrollArea>
        )}
      </GlassCard>
    </div>
  );
}
