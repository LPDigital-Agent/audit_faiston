'use client';

// =============================================================================
// Movimentacoes Page - SGA Inventory Module
// =============================================================================
// Movement hub: links to entry, exit, transfer, reservation, adjustment.
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
import {
  ArrowRightLeft,
  FileUp,
  Truck,
  RefreshCw,
  Calendar,
  AlertTriangle,
  ChevronRight,
  History,
} from 'lucide-react';
import { useMovements } from '@/hooks/ativos';
import { SGA_MOVEMENT_LABELS } from '@/lib/ativos/constants';

// =============================================================================
// Page Component
// =============================================================================

export default function MovimentacoesPage() {
  const { movements, isLoading, total } = useMovements();

  const movementTypes = [
    {
      title: 'Entrada',
      description: 'Internalização de materiais via NF',
      icon: FileUp,
      color: 'text-green-400',
      bgColor: 'bg-green-500/20',
      href: '/ferramentas/ativos/estoque/movimentacoes/entrada',
    },
    {
      title: 'Saída / Expedição',
      description: 'Envio de materiais para campo',
      icon: Truck,
      color: 'text-blue-light',
      bgColor: 'bg-blue-mid/20',
      href: '/ferramentas/ativos/estoque/movimentacoes/saida',
    },
    {
      title: 'Transferência',
      description: 'Movimentação entre locais',
      icon: ArrowRightLeft,
      color: 'text-magenta-mid',
      bgColor: 'bg-magenta-dark/20',
      href: '/ferramentas/ativos/estoque/movimentacoes/transferencia',
    },
    {
      title: 'Reserva',
      description: 'Bloqueio temporário de materiais',
      icon: Calendar,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-500/20',
      href: '/ferramentas/ativos/estoque/movimentacoes/reserva',
    },
    {
      title: 'Ajuste',
      description: 'Correção de saldos (requer aprovação)',
      icon: AlertTriangle,
      color: 'text-red-400',
      bgColor: 'bg-red-500/20',
      href: '/ferramentas/ativos/estoque/movimentacoes/ajuste',
    },
  ];

  // Recent movements
  const recentMovements = movements.slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Movimentações
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Gerencie todas as operações de estoque
          </p>
        </div>
        <Badge variant="outline" className="w-fit">
          <History className="w-3 h-3 mr-1" />
          {isLoading ? '...' : total} movimentações registradas
        </Badge>
      </div>

      {/* Movement Types Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {movementTypes.map((type, index) => (
          <motion.div
            key={type.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Link href={type.href}>
              <GlassCard className="h-full hover:border-blue-mid/50 transition-colors cursor-pointer group">
                <GlassCardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className={`p-3 rounded-lg ${type.bgColor}`}>
                      <type.icon className={`w-6 h-6 ${type.color}`} />
                    </div>
                    <ChevronRight className="w-5 h-5 text-text-muted group-hover:text-blue-light transition-colors" />
                  </div>
                  <div className="mt-4">
                    <h3 className="text-lg font-semibold text-text-primary group-hover:text-blue-light transition-colors">
                      {type.title}
                    </h3>
                    <p className="text-sm text-text-muted mt-1">
                      {type.description}
                    </p>
                  </div>
                </GlassCardContent>
              </GlassCard>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Recent Movements */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-blue-light" />
              <GlassCardTitle>Movimentações Recentes</GlassCardTitle>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/movimentacoes/historico">
                Ver histórico completo
              </Link>
            </Button>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="w-6 h-6 text-text-muted animate-spin" />
            </div>
          ) : recentMovements.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <ArrowRightLeft className="w-12 h-12 text-text-muted mb-3" />
              <p className="text-sm text-text-muted">
                Nenhuma movimentação registrada
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {recentMovements.map((movement, index) => (
                <motion.div
                  key={movement.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-mid/20 flex items-center justify-center">
                      <ArrowRightLeft className="w-5 h-5 text-blue-light" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-text-primary">
                        {SGA_MOVEMENT_LABELS[movement.type] || movement.type}
                      </p>
                      <p className="text-xs text-text-muted">
                        {movement.part_number} • Qtd: {movement.quantity}
                      </p>
                    </div>
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
                </motion.div>
              ))}
            </div>
          )}
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
