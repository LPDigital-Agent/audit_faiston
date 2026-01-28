"use client";

// =============================================================================
// Reversa Page - Reverse Logistics Management
// =============================================================================
// Manages reverse logistics with three workflow stages:
// - Pendentes: Tiflux tickets awaiting reversa generation
// - Em Andamento: Generated reversas awaiting delivery
// - Concluídas: Delivered reversas
// =============================================================================

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardContent } from "@/components/shared/glass-card";
import { AssetManagementHeader } from "@/components/ferramentas/ativos/asset-management-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getTifluxTicketsForReversa, getReversas } from '@/services/carrierAgentcore';
import type { TifluxTicket, TifluxTicketDetail, SGAReversa } from '@/lib/ativos/types';
import { ReversaFormModal } from '@/components/ferramentas/ativos/modals/ReversaFormModal';
import { ReversaDetailsModal } from '@/components/ferramentas/ativos/modals/ReversaDetailsModal';
import { useToast } from '@/components/ui/use-toast';
import { Input } from "@/components/ui/input";
import {
  RefreshCw,
  MapPin,
  Loader2,
  InboxIcon,
  Calendar,
  User,
  Package,
  CheckCircle,
  Clock,
  Truck,
  Search,
  Filter,
  Building2,
  FileText,
} from "lucide-react";
import { motion } from "framer-motion";

/**
 * Reversa Page - Reverse Logistics with Tiflux Integration
 *
 * Three tabs for workflow management:
 * 1. Pendentes: Tiflux tickets ready for reversa generation
 * 2. Em Andamento: Active reversas (status: gerado)
 * 3. Concluídas: Delivered reversas (status: entregue)
 */
export default function ReversaPage() {
  const [activeTab, setActiveTab] = useState<string>("pendentes");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedTicket, setSelectedTicket] = useState<TifluxTicketDetail | null>(null);
  const [selectedDetailsTicket, setSelectedDetailsTicket] = useState<TifluxTicket | null>(null);
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const { toast } = useToast();

  // Fetch Tiflux tickets for "Pendentes" tab
  const {
    data: tifluxData,
    isLoading: tifluxLoading,
    refetch: refetchTiflux
  } = useQuery({
    queryKey: ['tiflux-tickets-reversa'],
    queryFn: async () => {
      const response = await getTifluxTicketsForReversa();
      return response.data;
    },
  });

  // Fetch reversas for "Em Andamento" and "Concluídas" tabs
  const {
    data: reversasData,
    isLoading: reversasLoading
  } = useQuery({
    queryKey: ['reversas'],
    queryFn: async () => {
      const response = await getReversas();
      return response.data;
    },
  });

  // Filter function for search
  const filterBySearch = <T extends { technician_name?: string; order_code?: string; tracking_code?: string }>(
    items: T[],
    query: string
  ): T[] => {
    if (!query.trim()) return items;
    const lowerQuery = query.toLowerCase();
    return items.filter((item) => {
      return (
        item.technician_name?.toLowerCase().includes(lowerQuery) ||
        item.order_code?.toLowerCase().includes(lowerQuery) ||
        item.tracking_code?.toLowerCase().includes(lowerQuery)
      );
    });
  };

  // Helper function to filter tickets by search
  const filterTicketsBySearch = (tickets: TifluxTicket[]): TifluxTicket[] => {
    if (!searchQuery.trim()) return tickets;
    const lowerQuery = searchQuery.toLowerCase();
    return tickets.filter((ticket: TifluxTicket) => (
      String(ticket.ticket_number).includes(lowerQuery) ||
      ticket.technician?.nome?.toLowerCase().includes(lowerQuery) ||
      ticket.technician?.cidade?.toLowerCase().includes(lowerQuery) ||
      ticket.client_name?.toLowerCase().includes(lowerQuery) ||
      ticket.title?.toLowerCase().includes(lowerQuery)
    ));
  };

  // F8: Filter Tiflux tickets by status
  // Pendentes: New tickets with status "Opened" (need reversa generation)
  const ticketsPendentes = filterTicketsBySearch(
    tifluxData?.tickets?.filter(
      (ticket: TifluxTicket) => ticket.status === "Opened"
    ) || []
  );

  // Tickets with status "Aguardando Reversa" (already in reversa process)
  // These show in the Tiflux section of Em Andamento tab
  const ticketsAguardandoReversa = filterTicketsBySearch(
    tifluxData?.tickets?.filter(
      (ticket: TifluxTicket) => ticket.status === "Aguardando Reversa"
    ) || []
  );

  // Filter reversas by status
  const reversasEmAndamento = filterBySearch(
    reversasData?.reversas?.filter(
      (r: SGAReversa) => r.status === 'pendente' || r.status === 'postado' || r.status === 'em_transito' || r.status === 'ocorrencia'
    ) || [],
    searchQuery
  );

  const reversasConcluidas = filterBySearch(
    reversasData?.reversas?.filter(
      (r: SGAReversa) => r.status === 'entregue'
    ) || [],
    searchQuery
  );

  // F10: Handle ticket card click - Use cached data for instant modal open
  // Opens ReversaFormModal for "Opened" tickets, ReversaDetailsModal for "Aguardando Reversa"
  const handleTicketClick = (ticketNumber: number) => {
    // Find ticket from already-loaded data (instant, no API call needed)
    const allTickets = tifluxData?.tickets || [];
    const ticket = allTickets.find((t: TifluxTicket) => t.ticket_number === ticketNumber);

    if (ticket) {
      if (ticket.status === "Opened") {
        // Open form modal for creating reversa
        setSelectedTicket(ticket as TifluxTicketDetail);
        setIsFormModalOpen(true);
      } else {
        // Open details modal for viewing (Aguardando Reversa and others)
        setSelectedDetailsTicket(ticket);
      }
    } else {
      // Fallback: ticket not found in cache (shouldn't happen in normal flow)
      toast({
        title: "Ticket nao encontrado",
        description: "O ticket nao foi encontrado nos dados carregados.",
        variant: "destructive",
      });
    }
  };

  // Handle reversa card click
  const handleReversaClick = (reversaId: string) => {
    console.log("Reversa clicked:", reversaId);
    // TODO: Open modal to view reversa details
  };

  // Handle refresh
  const handleRefresh = () => {
    if (activeTab === "pendentes") {
      refetchTiflux();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <AssetManagementHeader
        title="Logística Reversa"
        subtitle="Gerencie devoluções de equipamentos de campo"
        primaryAction={{
          label: "Atualizar",
          onClick: handleRefresh,
          icon: <RefreshCw className="w-4 h-4" />,
        }}
      />

      {/* Search Bar */}
      <GlassCard className="p-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              placeholder="Buscar por ticket, técnico ou código..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-white/5 border-border"
            />
          </div>
          <Button variant="outline" size="sm" className="border-border">
            <Filter className="w-4 h-4 mr-2" />
            Filtros
          </Button>
        </div>
      </GlassCard>

      {/* Tabs */}
      <GlassCard>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-white/5">
            <TabsTrigger value="pendentes" className="data-[state=active]:bg-magenta-light/20">
              Pendentes
              {ticketsPendentes.length > 0 && (
                <Badge variant="outline" className="ml-2">
                  {ticketsPendentes.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="andamento" className="data-[state=active]:bg-blue-500/20">
              Em Andamento
              {(ticketsAguardandoReversa.length + reversasEmAndamento.length) > 0 && (
                <Badge variant="outline" className="ml-2">
                  {ticketsAguardandoReversa.length + reversasEmAndamento.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="concluidas" className="data-[state=active]:bg-green-500/20">
              Concluídas
              {reversasConcluidas.length > 0 && (
                <Badge variant="outline" className="ml-2">
                  {reversasConcluidas.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Pendentes Tab - Tiflux Tickets */}
          <TabsContent value="pendentes" className="mt-6">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-magenta-light" />
                  <GlassCardTitle>Tickets Pendentes</GlassCardTitle>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchTiflux()}
                  disabled={tifluxLoading}
                  className="border-border"
                >
                  <RefreshCw className={`w-4 h-4 ${tifluxLoading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              {tifluxLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-magenta-light animate-spin" />
                </div>
              ) : ticketsPendentes.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {ticketsPendentes.map((ticket: TifluxTicket, index: number) => (
                    <motion.div
                      key={ticket.ticket_number}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => handleTicketClick(ticket.ticket_number)}
                      className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      {/* F9: Ticket Number + Stage Badge */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold text-magenta-light">
                          #{ticket.ticket_number}
                        </p>
                        <Badge variant="outline" className="text-xs">
                          {ticket.stage}
                        </Badge>
                      </div>

                      {/* F9: Client Name */}
                      {ticket.client_name && (
                        <p className="text-sm font-medium text-text-primary truncate mb-1" title={ticket.client_name}>
                          {ticket.client_name.length > 35
                            ? `${ticket.client_name.substring(0, 35)}...`
                            : ticket.client_name}
                        </p>
                      )}

                      {/* F9: Title/Equipment */}
                      {ticket.title && (
                        <div className="flex items-center gap-2 text-xs text-text-muted mb-3">
                          <FileText className="w-3 h-3 shrink-0" />
                          <span className="truncate" title={ticket.title}>
                            {ticket.title.length > 30
                              ? `${ticket.title.substring(0, 30)}...`
                              : ticket.title}
                          </span>
                        </div>
                      )}

                      <div className="border-t border-border/50 pt-3 mt-2 space-y-2">
                        {/* Technician Info */}
                        {ticket.technician?.nome && (
                          <div className="flex items-center gap-2 text-sm text-text-primary">
                            <User className="w-4 h-4 text-text-muted shrink-0" />
                            <span className="truncate">{ticket.technician.nome || "Técnico não informado"}</span>
                          </div>
                        )}

                        {/* Location */}
                        {ticket.technician?.cidade && ticket.technician?.uf && (
                          <div className="flex items-center gap-2 text-sm text-text-muted">
                            <MapPin className="w-4 h-4 shrink-0" />
                            <span className="truncate">
                              {ticket.technician.cidade}, {ticket.technician.uf}
                            </span>
                          </div>
                        )}

                        {/* Date */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <Calendar className="w-3 h-3 shrink-0" />
                          <span>
                            {new Date(ticket.created_at).toLocaleDateString('pt-BR')}
                          </span>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                  <p className="text-sm font-medium text-text-primary mb-1">
                    Nenhum ticket pendente
                  </p>
                  <p className="text-xs text-text-muted">
                    Tickets com status &quot;Opened&quot; aparecerão aqui
                  </p>
                </div>
              )}
            </GlassCardContent>
          </TabsContent>

          {/* Em Andamento Tab - Aguardando Reversa tickets + Active Reversas */}
          <TabsContent value="andamento" className="mt-6 space-y-6">
            {/* Section 1: Tiflux Tickets Aguardando Reversa */}
            {ticketsAguardandoReversa.length > 0 && (
              <div>
                <GlassCardHeader>
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-amber-400" />
                    <GlassCardTitle>Aguardando Reversa (Tiflux)</GlassCardTitle>
                    <Badge variant="outline" className="ml-2 text-xs bg-amber-500/20 text-amber-400">
                      {ticketsAguardandoReversa.length}
                    </Badge>
                  </div>
                </GlassCardHeader>

                <GlassCardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {ticketsAguardandoReversa.map((ticket: TifluxTicket, index: number) => (
                      <motion.div
                        key={ticket.ticket_number}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        onClick={() => handleTicketClick(ticket.ticket_number)}
                        className="bg-white/5 border border-amber-500/30 rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                      >
                        {/* Ticket Number + Status Badge */}
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-sm font-semibold text-amber-400">
                            #{ticket.ticket_number}
                          </p>
                          <Badge variant="outline" className="text-xs bg-amber-500/20 text-amber-400">
                            {ticket.status}
                          </Badge>
                        </div>

                        {/* Client Name */}
                        {ticket.client_name && (
                          <p className="text-sm font-medium text-text-primary truncate mb-1" title={ticket.client_name}>
                            {ticket.client_name.length > 35
                              ? `${ticket.client_name.substring(0, 35)}...`
                              : ticket.client_name}
                          </p>
                        )}

                        {/* Title/Equipment */}
                        {ticket.title && (
                          <div className="flex items-center gap-2 text-xs text-text-muted mb-3">
                            <FileText className="w-3 h-3 shrink-0" />
                            <span className="truncate" title={ticket.title}>
                              {ticket.title.length > 30
                                ? `${ticket.title.substring(0, 30)}...`
                                : ticket.title}
                            </span>
                          </div>
                        )}

                        <div className="border-t border-border/50 pt-3 mt-2 space-y-2">
                          {ticket.technician?.nome && (
                            <div className="flex items-center gap-2 text-sm text-text-primary">
                              <User className="w-4 h-4 text-text-muted shrink-0" />
                              <span className="truncate">{ticket.technician.nome}</span>
                            </div>
                          )}

                          {ticket.technician?.cidade && ticket.technician?.uf && (
                            <div className="flex items-center gap-2 text-sm text-text-muted">
                              <MapPin className="w-4 h-4 shrink-0" />
                              <span className="truncate">
                                {ticket.technician.cidade}, {ticket.technician.uf}
                              </span>
                            </div>
                          )}

                          {ticket.desk && (
                            <div className="flex items-center gap-2 text-xs text-text-muted">
                              <Building2 className="w-3 h-3 shrink-0" />
                              <span className="truncate">{ticket.desk}</span>
                            </div>
                          )}

                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <Calendar className="w-3 h-3 shrink-0" />
                            <span>
                              {new Date(ticket.created_at).toLocaleDateString('pt-BR')}
                            </span>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </GlassCardContent>
              </div>
            )}

            {/* Section 2: SGA Reversas em Andamento */}
            <div>
              <GlassCardHeader>
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-blue-400" />
                  <GlassCardTitle>Reversas em Trânsito</GlassCardTitle>
                  {reversasEmAndamento.length > 0 && (
                    <Badge variant="outline" className="ml-2 text-xs">
                      {reversasEmAndamento.length}
                    </Badge>
                  )}
                </div>
              </GlassCardHeader>

              <GlassCardContent>
                {reversasLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
                  </div>
                ) : reversasEmAndamento.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {reversasEmAndamento.map((reversa: SGAReversa, index: number) => (
                      <motion.div
                        key={reversa.reversa_id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        onClick={() => handleReversaClick(reversa.reversa_id)}
                        className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                      >
                        {/* Order Code */}
                        <div className="flex items-center justify-between mb-3">
                          <p className="text-sm font-semibold text-blue-400">
                            {reversa.order_code}
                          </p>
                          <Badge variant="outline" className="text-xs capitalize">
                            {reversa.status.replace('_', ' ')}
                          </Badge>
                        </div>

                        {/* Reversa Info */}
                        <div className="space-y-2">
                          {reversa.technician_name && (
                            <div className="flex items-center gap-2 text-sm text-text-primary">
                              <User className="w-4 h-4 text-text-muted shrink-0" />
                              <span className="truncate">{reversa.technician_name}</span>
                            </div>
                          )}

                          {reversa.origin.city && reversa.origin.state && (
                            <div className="flex items-center gap-2 text-sm text-text-muted">
                              <MapPin className="w-4 h-4 shrink-0" />
                              <span className="truncate">
                                {reversa.origin.city}, {reversa.origin.state}
                              </span>
                            </div>
                          )}

                          {reversa.tracking_code && (
                            <div className="flex items-center gap-2 text-xs text-text-muted">
                              <Package className="w-3 h-3 shrink-0" />
                              <span className="font-mono">{reversa.tracking_code}</span>
                            </div>
                          )}

                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <Calendar className="w-3 h-3 shrink-0" />
                            <span>
                              {new Date(reversa.created_at).toLocaleDateString('pt-BR')}
                            </span>
                          </div>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                    <p className="text-sm font-medium text-text-primary mb-1">
                      Nenhuma reversa em trânsito
                    </p>
                    <p className="text-xs text-text-muted">
                      Reversas com código de rastreio aparecerão aqui
                    </p>
                  </div>
                )}
              </GlassCardContent>
            </div>
          </TabsContent>

          {/* Concluídas Tab - Delivered Reversas */}
          <TabsContent value="concluidas" className="mt-6">
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-400" />
                <GlassCardTitle>Reversas Concluídas</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              {reversasLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-green-400 animate-spin" />
                </div>
              ) : reversasConcluidas.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {reversasConcluidas.map((reversa: SGAReversa, index: number) => (
                    <motion.div
                      key={reversa.reversa_id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => handleReversaClick(reversa.reversa_id)}
                      className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      {/* Order Code */}
                      <div className="flex items-center justify-between mb-3">
                        <p className="text-sm font-semibold text-green-400">
                          {reversa.order_code}
                        </p>
                        <Badge variant="outline" className="text-xs bg-green-500/20 text-green-400">
                          Entregue
                        </Badge>
                      </div>

                      {/* Reversa Info */}
                      <div className="space-y-2">
                        {reversa.technician_name && (
                          <div className="flex items-center gap-2 text-sm text-text-primary">
                            <User className="w-4 h-4 text-text-muted shrink-0" />
                            <span className="truncate">{reversa.technician_name}</span>
                          </div>
                        )}

                        {reversa.origin.city && reversa.origin.state && (
                          <div className="flex items-center gap-2 text-sm text-text-muted">
                            <MapPin className="w-4 h-4 shrink-0" />
                            <span className="truncate">
                              {reversa.origin.city}, {reversa.origin.state}
                            </span>
                          </div>
                        )}

                        {reversa.delivered_at && (
                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <Calendar className="w-3 h-3 shrink-0" />
                            <span>
                              Entregue em {new Date(reversa.delivered_at).toLocaleDateString('pt-BR')}
                            </span>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                  <p className="text-sm font-medium text-text-primary mb-1">
                    Nenhuma reversa concluída
                  </p>
                  <p className="text-xs text-text-muted">
                    Reversas entregues aparecerão aqui
                  </p>
                </div>
              )}
            </GlassCardContent>
          </TabsContent>
        </Tabs>
      </GlassCard>

      {/* F10: Reversa Form Modal - For creating new reversas (Opened tickets) */}
      <ReversaFormModal
        open={isFormModalOpen}
        onOpenChange={setIsFormModalOpen}
        ticket={selectedTicket}
      />

      {/* Reversa Details Modal - For viewing existing reversas (Aguardando Reversa tickets) */}
      <ReversaDetailsModal
        ticket={selectedDetailsTicket}
        onClose={() => setSelectedDetailsTicket(null)}
      />
    </div>
  );
}
