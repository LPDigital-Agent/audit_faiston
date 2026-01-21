'use client';

// =============================================================================
// PostingDetailsModal - SGA Expedicao Module
// =============================================================================
// Apple TV-style frosted glass modal for viewing posting details.
// Shows tracking info, carrier, pricing, destination, and status actions.
//
// Design: Frosted dark glass effect (backdrop-blur + rgba background)
// =============================================================================

import { useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Package,
  MapPin,
  Truck,
  Calendar,
  DollarSign,
  Hash,
  Copy,
  ExternalLink,
  Play,
  Check,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { toast } from '@/components/ui/use-toast';

// =============================================================================
// Types
// =============================================================================

export type ShippingOrderStatus = 'aguardando' | 'em_transito' | 'entregue' | 'cancelado';

export interface ShippingOrder {
  id: string;
  codigo: string;
  cliente: string;
  destino: { nome: string; cep?: string };
  status: ShippingOrderStatus;
  prioridade: string;
  responsavel: { nome: string };
  itens: Array<{
    ativoId: string;
    ativoCodigo: string;
    ativoNome: string;
    quantidade: number;
  }>;
  dataCriacao: string;
  dataPrevista: string;
  carrier?: string;
  trackingCode?: string;
  price?: number;
}

interface PostingDetailsModalProps {
  /** The order to display, or null to close */
  order: ShippingOrder | null;
  /** Callback when modal should close */
  onClose: () => void;
  /** Callback to move order to next status */
  onMoveToNextStatus?: (orderId: string, currentStatus: ShippingOrderStatus) => void;
  /** Whether status update is pending */
  isUpdating?: boolean;
}

// =============================================================================
// Helpers
// =============================================================================

const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr || dateStr === '') return '—';
  try {
    return new Date(dateStr).toLocaleDateString('pt-BR');
  } catch {
    return '—';
  }
};

const getStatusConfig = (status: ShippingOrderStatus) => {
  switch (status) {
    case 'aguardando':
      return { label: 'Aguardando', className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' };
    case 'em_transito':
      return { label: 'Em Transito', className: 'bg-blue-500/20 text-blue-400 border-blue-500/30' };
    case 'entregue':
      return { label: 'Entregue', className: 'bg-green-500/20 text-green-400 border-green-500/30' };
    case 'cancelado':
      return { label: 'Cancelado', className: 'bg-red-500/20 text-red-400 border-red-500/30' };
    default:
      return { label: status, className: 'bg-gray-500/20 text-gray-400' };
  }
};

// =============================================================================
// Component
// =============================================================================

export function PostingDetailsModal({
  order,
  onClose,
  onMoveToNextStatus,
  isUpdating = false,
}: PostingDetailsModalProps) {
  const handleCopyTracking = useCallback(() => {
    if (order?.trackingCode) {
      navigator.clipboard.writeText(order.trackingCode);
      toast({ title: 'Codigo copiado!' });
    }
  }, [order?.trackingCode]);

  const handleOpenTracking = useCallback(() => {
    if (order?.trackingCode) {
      window.open(
        `https://rastreamento.correios.com.br/app/index.php?objeto=${order.trackingCode}`,
        '_blank'
      );
    }
  }, [order?.trackingCode]);

  const handleMoveStatus = useCallback(() => {
    if (order && onMoveToNextStatus) {
      onMoveToNextStatus(order.id, order.status);
      onClose();
    }
  }, [order, onMoveToNextStatus, onClose]);

  const statusConfig = order ? getStatusConfig(order.status) : null;

  return (
    <Dialog.Root open={!!order} onOpenChange={(open) => !open && onClose()}>
      <AnimatePresence>
        {order && (
          <Dialog.Portal forceMount>
            {/* Overlay - Frosted Glass Effect */}
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="fixed inset-0 z-50 bg-[#151720]/85 backdrop-blur-[24px]"
              />
            </Dialog.Overlay>

            {/* Modal Content */}
            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 10 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className={cn(
                  'fixed left-1/2 top-1/2 z-50 w-full max-w-[480px] -translate-x-1/2 -translate-y-1/2',
                  'bg-[#1a1d28]/90 backdrop-blur-xl',
                  'border border-white/[0.06] rounded-2xl shadow-2xl',
                  'p-6 max-h-[90vh] overflow-y-auto'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <Dialog.Title className="text-xl font-semibold text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-[#960A9C]/20 to-[#2226C0]/20 border border-white/[0.04]">
                      <Package className="w-5 h-5 text-[#00FAFB]" />
                    </div>
                    Detalhes da Postagem
                  </Dialog.Title>
                  <Dialog.Close asChild>
                    <button
                      className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                      aria-label="Fechar"
                    >
                      <X className="w-5 h-5 text-gray-400" />
                    </button>
                  </Dialog.Close>
                </div>

                {/* Content */}
                <div className="space-y-5">
                  {/* Order Code & Status */}
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                    <div>
                      <p className="text-lg font-semibold text-white">{order.codigo}</p>
                      <p className="text-sm text-gray-500">ID: {order.id.slice(0, 8)}...</p>
                    </div>
                    {statusConfig && (
                      <Badge className={cn('border', statusConfig.className)}>
                        {statusConfig.label}
                      </Badge>
                    )}
                  </div>

                  {/* Tracking Code */}
                  {order.trackingCode && (
                    <div className="p-4 rounded-xl bg-gradient-to-br from-[#00FAFB]/5 to-transparent border border-[#00FAFB]/20">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Hash className="w-4 h-4 text-[#00FAFB]" />
                          <span className="text-sm text-gray-400">Codigo de Rastreio</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium text-white">{order.trackingCode}</span>
                          <button
                            onClick={handleCopyTracking}
                            className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                            title="Copiar"
                          >
                            <Copy className="w-4 h-4 text-gray-400" />
                          </button>
                          <button
                            onClick={handleOpenTracking}
                            className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                            title="Rastrear"
                          >
                            <ExternalLink className="w-4 h-4 text-gray-400" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Carrier & Price */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Truck className="w-4 h-4 text-[#00FAFB]" />
                        <span className="text-sm text-gray-400">Transportadora</span>
                      </div>
                      <p className="font-medium text-white">{order.carrier || 'Correios'}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <DollarSign className="w-4 h-4 text-[#00FAFB]" />
                        <span className="text-sm text-gray-400">Valor do Frete</span>
                      </div>
                      <p className="font-medium text-white">R$ {order.price?.toFixed(2) || '0.00'}</p>
                    </div>
                  </div>

                  {/* Destination */}
                  <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                    <div className="flex items-center gap-2 mb-2">
                      <MapPin className="w-4 h-4 text-[#00FAFB]" />
                      <span className="text-sm text-gray-400">Destinatario</span>
                    </div>
                    <p className="font-medium text-white">{order.destino.nome}</p>
                    {order.destino.cep && (
                      <p className="text-sm text-gray-500 mt-1">CEP: {order.destino.cep}</p>
                    )}
                  </div>

                  {/* Dates */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Calendar className="w-4 h-4 text-[#00FAFB]" />
                        <span className="text-sm text-gray-400">Criado em</span>
                      </div>
                      <p className="font-medium text-white">{formatDate(order.dataCriacao)}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Calendar className="w-4 h-4 text-[#00FAFB]" />
                        <span className="text-sm text-gray-400">Previsao</span>
                      </div>
                      <p className="font-medium text-white">{formatDate(order.dataPrevista)}</p>
                    </div>
                  </div>

                  {/* Priority */}
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-[#00FAFB]" />
                      <span className="text-sm text-gray-400">Prioridade</span>
                    </div>
                    <Badge
                      className={cn(
                        'border',
                        order.prioridade === 'urgent'
                          ? 'bg-red-500/20 text-red-400 border-red-500/30'
                          : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                      )}
                    >
                      {order.prioridade === 'urgent' ? 'Urgente' : 'Normal'}
                    </Badge>
                  </div>

                  {/* Actions */}
                  {order.status !== 'entregue' && order.status !== 'cancelado' && onMoveToNextStatus && (
                    <div className="pt-2">
                      <Button
                        className={cn(
                          'w-full h-12 rounded-xl font-medium',
                          'bg-gradient-to-r from-[#960A9C] to-[#2226C0]',
                          'hover:from-[#a00ba6] hover:to-[#2830d4]',
                          'transition-all duration-200'
                        )}
                        onClick={handleMoveStatus}
                        disabled={isUpdating}
                      >
                        {isUpdating ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Atualizando...
                          </>
                        ) : order.status === 'aguardando' ? (
                          <>
                            <Play className="w-4 h-4 mr-2" />
                            Mover para Em Transito
                          </>
                        ) : (
                          <>
                            <Check className="w-4 h-4 mr-2" />
                            Marcar como Entregue
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
