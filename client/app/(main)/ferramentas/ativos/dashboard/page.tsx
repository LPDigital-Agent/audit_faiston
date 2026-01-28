"use client";

// =============================================================================
// Dashboard Page - Gestão de Ativos
// =============================================================================
// Main dashboard showing KPIs, recent movements, alerts, and quick actions.
// NOW USING REAL DATA FROM DYNAMODB - No more mock data!
// =============================================================================

import { BentoGrid, BentoItem } from "@/components/dashboard/bento-grid";
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardContent } from "@/components/shared/glass-card";
import { AssetStatsCard } from "@/components/ferramentas/ativos/asset-stats-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Package,
  PackageCheck,
  Truck,
  Wrench,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
  Clock,
  Plus,
  FileText,
  RefreshCcw,
  Loader2,
  InboxIcon,
  Activity,
} from "lucide-react";
import { formatCurrency } from "@/lib/ativos/constants";
import { useAssets, useMovements, useTaskInbox } from "@/hooks/ativos";
import { motion } from "framer-motion";
import Link from "next/link";

/**
 * Dashboard Page - Gestão de Ativos
 *
 * Now uses REAL data from DynamoDB via hooks:
 * - useAssets() for asset counts
 * - useMovements() for recent movements
 * - useTaskInbox() for alerts (HIL tasks)
 */

export default function AssetDashboardPage() {
  // Real data from DynamoDB
  const { assets, isLoading: assetsLoading } = useAssets();
  const { movements, isLoading: movementsLoading } = useMovements();
  const { tasks, tasksLoading } = useTaskInbox();

  // Calculate real KPIs from assets
  const totalAtivos = assets.length;
  const ativosDisponiveis = assets.filter(a => a.status === 'AVAILABLE').length;
  const ativosEmTransito = assets.filter(a => a.status === 'IN_TRANSIT').length;
  const ativosManutencao = assets.filter(a => a.status === 'IN_REPAIR').length;
  const ativosEmUso = assets.filter(a => a.status === 'WITH_CUSTOMER' || a.status === 'RESERVED').length;

  // Calculate total value - currently not stored in SGAAsset
  // TODO: Add unit_cost lookup from part_number when needed
  const valorTotal = 0;

  // Pending tasks as alerts
  const pendingAlerts = tasks.filter(t => t.status === 'PENDING').slice(0, 5);

  // Recent movements (last 5)
  const recentMovements = movements.slice(0, 5);

  const isLoading = assetsLoading || movementsLoading || tasksLoading;

  return (
    <div className="space-y-6">
      {/* KPI Stats Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <AssetStatsCard
          title="Total de Ativos"
          value={isLoading ? '-' : totalAtivos}
          icon={<Package className="w-5 h-5" />}
          color="blue"
          delay={0}
        />
        <AssetStatsCard
          title="Disponíveis"
          value={isLoading ? '-' : ativosDisponiveis}
          icon={<PackageCheck className="w-5 h-5" />}
          color="green"
          delay={1}
        />
        <AssetStatsCard
          title="Em Trânsito"
          value={isLoading ? '-' : ativosEmTransito}
          icon={<Truck className="w-5 h-5" />}
          color="magenta"
          delay={2}
        />
        <AssetStatsCard
          title="Manutenção"
          value={isLoading ? '-' : ativosManutencao}
          icon={<Wrench className="w-5 h-5" />}
          color="yellow"
          delay={3}
        />
      </div>

      {/* Main Content Grid */}
      <BentoGrid>
        {/* Value Summary - 2 cols */}
        <BentoItem colSpan={2} delay={4}>
          <GlassCard className="h-full">
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                <GlassCardTitle>Valor do Patrimônio</GlassCardTitle>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <p className="text-3xl font-bold text-text-primary">
                    {isLoading ? '-' : formatCurrency(valorTotal)}
                  </p>
                  <p className="text-sm text-text-muted mt-1">Valor total dos ativos</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-text-muted">
                    -
                  </p>
                  <p className="text-sm text-text-muted mt-1">Depreciação (não calculada)</p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-border">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-muted">Taxa de utilização</span>
                  <span className="text-text-primary font-medium">
                    {totalAtivos > 0 ? ((ativosEmUso / totalAtivos) * 100).toFixed(1) : 0}%
                  </span>
                </div>
                <div className="mt-2 h-2 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: totalAtivos > 0 ? `${(ativosEmUso / totalAtivos) * 100}%` : '0%' }}
                    transition={{ delay: 0.5, duration: 0.8, ease: "easeOut" }}
                    className="h-full gradient-nexo rounded-full"
                  />
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>
        </BentoItem>

        {/* Quick Actions - 2 cols */}
        <BentoItem colSpan={2} delay={5}>
          <GlassCard className="h-full">
            <GlassCardHeader>
              <GlassCardTitle>Ações Rápidas</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="grid grid-cols-2 gap-3">
                <Link href="/ferramentas/ativos/estoque/movimentacoes/entrada">
                  <Button
                    variant="outline"
                    className="w-full h-auto py-4 flex flex-col items-center gap-2 border-border hover:bg-white/5 hover:border-blue-mid/30"
                  >
                    <div className="w-10 h-10 rounded-lg bg-blue-mid/20 flex items-center justify-center">
                      <Plus className="w-5 h-5 text-blue-light" />
                    </div>
                    <span className="text-sm">Novo Ativo</span>
                  </Button>
                </Link>
                <Link href="/ferramentas/ativos/estoque/movimentacoes/transferencia">
                  <Button
                    variant="outline"
                    className="w-full h-auto py-4 flex flex-col items-center gap-2 border-border hover:bg-white/5 hover:border-magenta-mid/30"
                  >
                    <div className="w-10 h-10 rounded-lg bg-magenta-mid/20 flex items-center justify-center">
                      <RefreshCcw className="w-5 h-5 text-magenta-light" />
                    </div>
                    <span className="text-sm">Transferir</span>
                  </Button>
                </Link>
                <Link href="/ferramentas/ativos/estoque/analytics">
                  <Button
                    variant="outline"
                    className="w-full h-auto py-4 flex flex-col items-center gap-2 border-border hover:bg-white/5 hover:border-green-500/30"
                  >
                    <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-green-400" />
                    </div>
                    <span className="text-sm">Relatório</span>
                  </Button>
                </Link>
                <Link href="/ferramentas/ativos/estoque/inventario">
                  <Button
                    variant="outline"
                    className="w-full h-auto py-4 flex flex-col items-center gap-2 border-border hover:bg-white/5 hover:border-yellow-500/30"
                  >
                    <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                      <Package className="w-5 h-5 text-yellow-400" />
                    </div>
                    <span className="text-sm">Inventário</span>
                  </Button>
                </Link>
                <Link href="/agent-control-room">
                  <Button
                    variant="outline"
                    className="w-full h-auto py-4 flex flex-col items-center gap-2 border-border hover:bg-white/5 hover:border-cyan-500/30"
                  >
                    <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                      <Activity className="w-5 h-5 text-cyan-400" />
                    </div>
                    <span className="text-sm">Neural Command Center</span>
                  </Button>
                </Link>
              </div>
            </GlassCardContent>
          </GlassCard>
        </BentoItem>

        {/* Recent Movements - 2 cols, 2 rows */}
        <BentoItem colSpan={2} rowSpan={2} delay={6}>
          <GlassCard className="h-full flex flex-col">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-blue-light" />
                  <GlassCardTitle>Movimentações Recentes</GlassCardTitle>
                </div>
                <Badge variant="outline" className="text-xs">
                  {recentMovements.length} items
                </Badge>
              </div>
            </GlassCardHeader>
            <ScrollArea className="flex-1">
              <div className="space-y-3 p-1">
                {movementsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
                  </div>
                ) : recentMovements.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <InboxIcon className="w-10 h-10 text-text-muted mb-2" />
                    <p className="text-sm text-text-muted">Nenhuma movimentação recente</p>
                    <p className="text-xs text-text-muted mt-1">
                      As movimentações aparecerão aqui
                    </p>
                  </div>
                ) : (
                  recentMovements.map((movement, index) => {
                    const typeColors: Record<string, string> = {
                      ENTRY: "bg-green-500/20 text-green-400",
                      EXIT: "bg-red-500/20 text-red-400",
                      TRANSFER: "bg-blue-500/20 text-blue-400",
                      ADJUSTMENT_IN: "bg-cyan-500/20 text-cyan-400",
                      ADJUSTMENT_OUT: "bg-orange-500/20 text-orange-400",
                      RESERVE: "bg-yellow-500/20 text-yellow-400",
                      RETURN: "bg-purple-500/20 text-purple-400",
                    };
                    const typeLabels: Record<string, string> = {
                      ENTRY: "Entrada",
                      EXIT: "Saída",
                      TRANSFER: "Transferência",
                      ADJUSTMENT_IN: "Ajuste +",
                      ADJUSTMENT_OUT: "Ajuste -",
                      RESERVE: "Reserva",
                      RETURN: "Devolução",
                    };

                    return (
                      <motion.div
                        key={movement.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.6 + index * 0.1 }}
                        className="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
                      >
                        <div className="text-xs text-text-muted w-12 shrink-0">
                          {movement.created_at ? new Date(movement.created_at).toLocaleTimeString("pt-BR", {
                            hour: "2-digit",
                            minute: "2-digit",
                          }) : '-'}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-text-primary truncate">
                            {movement.part_number || movement.part_number_id || "PN desconhecido"}
                          </p>
                          <p className="text-xs text-text-muted truncate">
                            Qtd: {movement.quantity} | {movement.reference_id || '-'}
                          </p>
                        </div>
                        <Badge className={typeColors[movement.type] || "bg-zinc-500/20 text-zinc-400"}>
                          {typeLabels[movement.type] || movement.type}
                        </Badge>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </ScrollArea>
            <div className="p-3 border-t border-border">
              <Link href="/ferramentas/ativos/estoque/movimentacoes">
                <Button variant="ghost" size="sm" className="w-full text-text-muted hover:text-text-primary">
                  Ver todas as movimentações
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </GlassCard>
        </BentoItem>

        {/* Alerts (HIL Tasks) - 2 cols, 2 rows */}
        <BentoItem colSpan={2} rowSpan={2} delay={7}>
          <GlassCard className="h-full flex flex-col">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-400" />
                  <GlassCardTitle>Tarefas Pendentes</GlassCardTitle>
                </div>
                <Badge variant="outline" className="text-xs bg-yellow-500/10 text-yellow-400 border-yellow-500/30">
                  {pendingAlerts.length}
                </Badge>
              </div>
            </GlassCardHeader>
            <ScrollArea className="flex-1">
              <div className="space-y-2 p-1">
                {tasksLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-text-muted" />
                  </div>
                ) : pendingAlerts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <AlertTriangle className="w-10 h-10 text-text-muted mb-2" />
                    <p className="text-sm text-text-muted">Nenhuma tarefa pendente</p>
                    <p className="text-xs text-text-muted mt-1">
                      Você está em dia!
                    </p>
                  </div>
                ) : (
                  pendingAlerts.map((task, index) => {
                    const priorityColors: Record<string, string> = {
                      HIGH: "border-l-red-500 bg-red-500/5",
                      URGENT: "border-l-red-500 bg-red-500/5",
                      MEDIUM: "border-l-yellow-500 bg-yellow-500/5",
                      LOW: "border-l-blue-500 bg-blue-500/5",
                    };

                    return (
                      <motion.div
                        key={task.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.7 + index * 0.1 }}
                        className={`p-3 rounded-lg border-l-4 ${priorityColors[task.priority] || priorityColors.MEDIUM} cursor-pointer hover:bg-white/5 transition-colors`}
                      >
                        <div className="flex items-start gap-2">
                          <AlertTriangle className={`w-4 h-4 mt-0.5 ${task.priority === 'HIGH' || task.priority === 'URGENT' ? 'text-red-400' : 'text-yellow-400'}`} />
                          <div className="flex-1">
                            <p className="text-sm text-text-primary">{task.title}</p>
                            <p className="text-xs text-text-muted mt-1">
                              {task.created_at ? new Date(task.created_at).toLocaleDateString("pt-BR") : '-'}
                            </p>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </ScrollArea>
            <div className="p-3 border-t border-border">
              <Link href="/ferramentas/ativos/estoque">
                <Button variant="ghost" size="sm" className="w-full text-text-muted hover:text-text-primary">
                  Ver todas as tarefas
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
            </div>
          </GlassCard>
        </BentoItem>
      </BentoGrid>
    </div>
  );
}
