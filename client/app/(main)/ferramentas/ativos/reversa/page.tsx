"use client";

// =============================================================================
// Reversa Page - Return Requests and Traceability
// =============================================================================
// Manages asset returns with timeline view and search functionality.
// NOW SHOWS REAL DATA OR EMPTY STATE - No more mock data!
// =============================================================================

import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardContent } from "@/components/shared/glass-card";
import { AssetManagementHeader } from "@/components/ferramentas/ativos/asset-management-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  RotateCcw,
  Search,
  Filter,
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  Package,
  ArrowRight,
  Calendar,
  User,
  AlertTriangle,
  InboxIcon,
} from "lucide-react";
import { motion } from "framer-motion";

/**
 * Reversa Page - Return Requests and Traceability
 *
 * Manages asset returns with timeline view and search functionality.
 * NOW USES REAL DATA - Empty state when no requests exist.
 */

// Types for return requests
type TimelineEvent = {
  id: string;
  data: string;
  descricao: string;
  responsavel: string;
};

type ReturnRequest = {
  id: string;
  codigo: string;
  ativoId: string;
  cliente: string;
  solicitante: { nome: string };
  motivo: string;
  status: string;
  descricao: string;
  dataSolicitacao: string;
  dataConclusao?: string;
  responsavel?: { nome: string };
  timeline: TimelineEvent[];
};

const statusConfig: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  solicitado: { label: "Solicitado", color: "bg-yellow-500/20 text-yellow-400", icon: Clock },
  em_transito: { label: "Em Trânsito", color: "bg-blue-500/20 text-blue-400", icon: RotateCcw },
  recebido: { label: "Recebido", color: "bg-green-500/20 text-green-400", icon: CheckCircle },
  rejeitado: { label: "Rejeitado", color: "bg-red-500/20 text-red-400", icon: XCircle },
};

const motivoLabels: Record<string, string> = {
  defeito: "Defeito",
  garantia: "Garantia",
  troca: "Troca",
  desuso: "Desuso",
  outro: "Outro",
};

export default function ReversaPage() {
  // Real data - empty until backend integration
  // TODO: Replace with useReturnRequests() hook when backend is ready
  const returnRequests: ReturnRequest[] = [];
  return (
    <div className="space-y-6">
      {/* Header */}
      <AssetManagementHeader
        title="Logística Reversa"
        subtitle="Gerencie devoluções e rastreabilidade de ativos"
        primaryAction={{
          label: "Nova Solicitação",
          onClick: () => console.log("Nova solicitação"),
          icon: <Plus className="w-4 h-4" />,
        }}
      />

      {/* Search and Filters */}
      <GlassCard className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              placeholder="Buscar por código, ativo ou solicitante..."
              className="pl-10 bg-white/5 border-border"
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="border-border">
              <Filter className="w-4 h-4 mr-2" />
              Filtros
            </Button>
          </div>
        </div>

        {/* Quick Filters */}
        <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
          <Badge variant="outline" className="cursor-pointer hover:bg-white/10 whitespace-nowrap">
            Todas ({returnRequests.length})
          </Badge>
          {Object.entries(statusConfig).map(([key, config]) => (
            <Badge
              key={key}
              variant="outline"
              className={`cursor-pointer hover:bg-white/10 ${config.color} whitespace-nowrap`}
            >
              {config.label} ({returnRequests.filter(r => r.status === key).length})
            </Badge>
          ))}
        </div>
      </GlassCard>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {Object.entries(statusConfig).map(([key, config], index) => {
          const StatusIcon = config.icon;
          const count = returnRequests.filter(r => r.status === key).length;

          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <GlassCard className="p-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${config.color.replace("text-", "bg-").replace("400", "500/20")}`}>
                    <StatusIcon className={`w-5 h-5 ${config.color.split(" ")[1]}`} />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-text-primary">{count}</p>
                    <p className="text-sm text-text-muted">{config.label}</p>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          );
        })}
      </div>

      {/* Return Requests List */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-magenta-light" />
              <GlassCardTitle>Solicitações de Devolução</GlassCardTitle>
            </div>
            <Badge variant="outline">{returnRequests.length} solicitações</Badge>
          </div>
        </GlassCardHeader>

        <ScrollArea className="max-h-[500px]">
          <div className="divide-y divide-border">
            {returnRequests.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                <p className="text-sm font-medium text-text-primary mb-1">
                  Nenhuma solicitação de devolução
                </p>
                <p className="text-xs text-text-muted">
                  As solicitações de devolução aparecerão aqui
                </p>
              </div>
            ) : (
              returnRequests.map((request, index) => {
                const config = statusConfig[request.status];
                const StatusIcon = config.icon;

                return (
                  <motion.div
                    key={request.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="p-4 hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <div className="flex items-start gap-4">
                      {/* Status Icon */}
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${config.color.replace("text-", "bg-").replace("400", "500/20")}`}>
                        <StatusIcon className={`w-5 h-5 ${config.color.split(" ")[1]}`} />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-medium text-text-primary">
                              {request.codigo}
                            </p>
                            <p className="text-xs text-text-muted mt-0.5">
                              Ativo: {request.ativoId}
                            </p>
                          </div>
                          <Badge className={config.color}>
                            {config.label}
                          </Badge>
                        </div>

                        {/* Details */}
                        <div className="flex flex-wrap gap-4 mt-3 text-xs text-text-muted">
                          <div className="flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            <span>{motivoLabels[request.motivo]}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            <span>{request.solicitante.nome}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            <span>{new Date(request.dataSolicitacao).toLocaleDateString("pt-BR")}</span>
                          </div>
                        </div>

                        {/* Timeline Preview */}
                        {request.timeline.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-border">
                            <p className="text-xs text-text-muted mb-2">Última atualização:</p>
                            <p className="text-xs text-text-secondary">
                              {request.timeline[request.timeline.length - 1].descricao}
                            </p>
                          </div>
                        )}
                      </div>

                      {/* Action */}
                      <Button variant="ghost" size="sm" className="shrink-0">
                        <ArrowRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </GlassCard>
    </div>
  );
}
