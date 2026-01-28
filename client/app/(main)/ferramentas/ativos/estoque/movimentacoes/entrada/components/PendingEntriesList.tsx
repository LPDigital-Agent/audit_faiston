'use client';

// =============================================================================
// PendingEntriesList - Shared Component for Entrada Tabs
// =============================================================================
// Displays list of pending NF entries awaiting confirmation or project assignment.
// Shared across all entrada tabs.
// =============================================================================

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import {
  AlertTriangle,
  RefreshCw,
  Briefcase,
  FolderPlus,
} from 'lucide-react';
import type { NFEntryStatus, PendingNFEntry } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface PendingEntriesListProps {
  entries: PendingNFEntry[];
  isLoading: boolean;
  onAssignProject: (entryId: string) => void;
  onReview: (entryId: string) => void;
}

// =============================================================================
// Helper Functions
// =============================================================================

function getStatusBadge(status: NFEntryStatus) {
  switch (status) {
    case 'PENDING_PROJECT':
      return <Badge className="bg-orange-500/20 text-orange-400">Aguardando Projeto</Badge>;
    case 'PENDING_APPROVAL':
      return <Badge className="bg-yellow-500/20 text-yellow-400">Aguardando Aprovacao</Badge>;
    case 'PENDING_CONFIRMATION':
    case 'PENDING':
      return <Badge className="bg-blue-500/20 text-blue-400">Aguardando Confirmacao</Badge>;
    case 'PROCESSING':
      return <Badge className="bg-purple-500/20 text-purple-400">Processando</Badge>;
    case 'CONFIRMED':
    case 'COMPLETED':
      return <Badge className="bg-green-500/20 text-green-400">Confirmado</Badge>;
    case 'REJECTED':
    case 'CANCELLED':
      return <Badge className="bg-red-500/20 text-red-400">Cancelado</Badge>;
    default:
      return <Badge className="bg-gray-500/20 text-gray-400">{status}</Badge>;
  }
}

// =============================================================================
// Component
// =============================================================================

export function PendingEntriesList({
  entries,
  isLoading,
  onAssignProject,
  onReview,
}: PendingEntriesListProps) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-400" />
          <GlassCardTitle>Entradas Pendentes</GlassCardTitle>
          <Badge variant="destructive">{entries.length}</Badge>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 text-text-muted animate-spin" />
          </div>
        ) : (
          <div className="space-y-2">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center justify-between p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-medium text-text-primary">
                      NF {entry.nf_number}
                    </p>
                    {getStatusBadge(entry.status)}
                  </div>
                  <p className="text-xs text-text-muted">
                    {entry.total_items} itens - {entry.supplier_name} -{' '}
                    {new Date(entry.uploaded_at).toLocaleDateString('pt-BR')}
                  </p>
                  {entry.project_name && (
                    <p className="text-xs text-text-muted mt-0.5">
                      <Briefcase className="w-3 h-3 inline mr-1" />
                      {entry.project_name}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {entry.status === 'PENDING_PROJECT' ? (
                    <Button
                      size="sm"
                      className="bg-orange-500/20 hover:bg-orange-500/30 text-orange-400"
                      onClick={() => onAssignProject(entry.id)}
                    >
                      <FolderPlus className="w-4 h-4 mr-1" />
                      Atribuir Projeto
                    </Button>
                  ) : (
                    <Button size="sm" onClick={() => onReview(entry.id)}>
                      Revisar
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCardContent>
    </GlassCard>
  );
}
