'use client';

// =============================================================================
// ReversaDetailsModal - View Reversa Details (Read-Only)
// =============================================================================
// Modal for viewing reversa ticket details when status is "Aguardando Reversa".
// Shows tracking code, status, technician info, and observacoes (read-only).
//
// Design: Frosted dark glass effect matching PostingDetailsModal
// =============================================================================

import { useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Package,
  MapPin,
  Calendar,
  Copy,
  ExternalLink,
  User,
  Phone,
  FileText,
  Building2,
  Clock,
  Truck,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { toast } from '@/components/ui/use-toast';
import type { TifluxTicket } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface ReversaDetailsModalProps {
  /** The ticket to display, or null to close */
  ticket: TifluxTicket | null;
  /** Callback when modal should close */
  onClose: () => void;
}

// =============================================================================
// Helpers
// =============================================================================

const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr || dateStr === '') return '\u2014';
  try {
    return new Date(dateStr).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '\u2014';
  }
};

const getStatusConfig = (status: string) => {
  switch (status) {
    case 'Opened':
      return { label: 'Aberto', className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' };
    case 'Aguardando Reversa':
      return { label: 'Aguardando Reversa', className: 'bg-amber-500/20 text-amber-400 border-amber-500/30' };
    case 'Em Transito':
      return { label: 'Em Transito', className: 'bg-blue-500/20 text-blue-400 border-blue-500/30' };
    case 'Entregue':
      return { label: 'Entregue', className: 'bg-green-500/20 text-green-400 border-green-500/30' };
    default:
      return { label: status, className: 'bg-gray-500/20 text-gray-400 border-gray-500/30' };
  }
};

// =============================================================================
// Component
// =============================================================================

export function ReversaDetailsModal({
  ticket,
  onClose,
}: ReversaDetailsModalProps) {
  const handleCopyTicketNumber = useCallback(() => {
    if (ticket?.ticket_number) {
      navigator.clipboard.writeText(String(ticket.ticket_number));
      toast({ title: 'Numero do ticket copiado!' });
    }
  }, [ticket]);

  const handleOpenTiflux = useCallback(() => {
    if (ticket?.ticket_number) {
      window.open(
        `https://app.tiflux.com/v/tickets/${ticket.ticket_number}/basic_info`,
        '_blank'
      );
    }
  }, [ticket]);

  const handleCopyTracking = useCallback(() => {
    if (ticket?.tracking_code) {
      navigator.clipboard.writeText(ticket.tracking_code);
      toast({ title: 'Codigo de rastreio copiado!' });
    }
  }, [ticket]);

  const handleOpenTracking = useCallback(() => {
    if (ticket?.tracking_code) {
      window.open(
        `https://rastreamento.correios.com.br/app/index.php?objeto=${ticket.tracking_code}`,
        '_blank'
      );
    }
  }, [ticket]);

  const statusConfig = ticket ? getStatusConfig(ticket.status) : null;

  return (
    <Dialog.Root open={!!ticket} onOpenChange={(open) => !open && onClose()}>
      <AnimatePresence>
        {ticket && (
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
                  'fixed left-1/2 top-1/2 z-50 w-full max-w-[520px] -translate-x-1/2 -translate-y-1/2',
                  'bg-[#1a1d28]/90 backdrop-blur-xl',
                  'border border-white/[0.06] rounded-2xl shadow-2xl',
                  'p-6 max-h-[90vh] overflow-y-auto'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <Dialog.Title className="text-xl font-semibold text-white flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-white/[0.04]">
                      <Package className="w-5 h-5 text-amber-400" />
                    </div>
                    Detalhes da Reversa
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
                  {/* Ticket Number & Status */}
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                    <div>
                      <p className="text-lg font-semibold text-white">#{ticket.ticket_number}</p>
                      <p className="text-sm text-gray-500">{ticket.stage}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {statusConfig && (
                        <Badge className={cn('border', statusConfig.className)}>
                          {statusConfig.label}
                        </Badge>
                      )}
                      <button
                        onClick={handleCopyTicketNumber}
                        className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                        title="Copiar numero"
                      >
                        <Copy className="w-4 h-4 text-gray-400" />
                      </button>
                      <button
                        onClick={handleOpenTiflux}
                        className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
                        title="Abrir no Tiflux"
                      >
                        <ExternalLink className="w-4 h-4 text-gray-400" />
                      </button>
                    </div>
                  </div>

                  {/* Tracking Code */}
                  <div className="p-4 rounded-xl bg-gradient-to-br from-green-500/5 to-transparent border border-green-500/20">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Truck className="w-4 h-4 text-green-400" />
                        <span className="text-sm text-gray-400">Codigo de Rastreio</span>
                      </div>
                      {ticket.tracking_code && (
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium text-white">{ticket.tracking_code}</span>
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
                      )}
                    </div>
                  </div>

                  {/* Client Info */}
                  {ticket.client_name && (
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-gray-400">Cliente</span>
                      </div>
                      <p className="font-medium text-white">{ticket.client_name}</p>
                    </div>
                  )}

                  {/* Title/Description */}
                  {ticket.title && (
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-gray-400">Titulo</span>
                      </div>
                      <p className="font-medium text-white text-sm">{ticket.title}</p>
                    </div>
                  )}

                  {/* Technician Info Section */}
                  {ticket.technician && (
                    <div className="p-4 rounded-xl bg-gradient-to-br from-amber-500/5 to-transparent border border-amber-500/20">
                      <div className="flex items-center gap-2 mb-3">
                        <User className="w-4 h-4 text-amber-400" />
                        <span className="text-sm font-medium text-amber-400">Dados do Tecnico</span>
                      </div>

                      <div className="space-y-3">
                        {/* Name */}
                        {ticket.technician.nome && (
                          <div>
                            <p className="text-xs text-gray-500 mb-0.5">Nome</p>
                            <p className="text-sm font-medium text-white">{ticket.technician.nome}</p>
                          </div>
                        )}

                        {/* CPF */}
                        {ticket.technician.cpf && (
                          <div>
                            <p className="text-xs text-gray-500 mb-0.5">CPF</p>
                            <p className="text-sm font-mono text-white">{ticket.technician.cpf}</p>
                          </div>
                        )}

                        {/* Phone */}
                        {ticket.technician.telefone && (
                          <div className="flex items-center gap-2">
                            <Phone className="w-3 h-3 text-gray-500" />
                            <p className="text-sm text-white">{ticket.technician.telefone}</p>
                          </div>
                        )}

                        {/* Address */}
                        {(ticket.technician.endereco || ticket.technician.cidade) && (
                          <div className="flex items-start gap-2">
                            <MapPin className="w-3 h-3 text-gray-500 mt-0.5" />
                            <div>
                              {ticket.technician.endereco && (
                                <p className="text-sm text-white">
                                  {ticket.technician.endereco}
                                  {ticket.technician.numero && `, ${ticket.technician.numero}`}
                                </p>
                              )}
                              {ticket.technician.bairro && (
                                <p className="text-xs text-gray-400">{ticket.technician.bairro}</p>
                              )}
                              {(ticket.technician.cidade || ticket.technician.uf) && (
                                <p className="text-xs text-gray-400">
                                  {ticket.technician.cidade}
                                  {ticket.technician.uf && ` - ${ticket.technician.uf}`}
                                </p>
                              )}
                              {ticket.technician.cep && (
                                <p className="text-xs text-gray-500">CEP: {ticket.technician.cep}</p>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Dates */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Calendar className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-gray-400">Criado em</span>
                      </div>
                      <p className="font-medium text-white text-sm">{formatDate(ticket.created_at)}</p>
                    </div>
                    <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                      <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-4 h-4 text-amber-400" />
                        <span className="text-sm text-gray-400">Atualizado</span>
                      </div>
                      <p className="font-medium text-white text-sm">{formatDate(ticket.updated_at)}</p>
                    </div>
                  </div>

                  </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
