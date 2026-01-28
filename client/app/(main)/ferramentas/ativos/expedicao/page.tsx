"use client";

// =============================================================================
// Expedição Page - Shipping Orders Management (Tiflux Integration)
// =============================================================================
// Tab-based view matching the Reversa module style:
// - Pendentes: Tiflux tickets awaiting postage (Enviado/Enviar Logistica)
// - Em Andamento: Postages created + in transit
// - Concluídas: Delivered postages
// =============================================================================

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard, GlassCardHeader, GlassCardTitle, GlassCardContent } from "@/components/shared/glass-card";
import { AssetManagementHeader } from "@/components/ferramentas/ativos/asset-management-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Truck,
  Clock,
  CheckCircle,
  Package,
  MapPin,
  Calendar,
  InboxIcon,
  Loader2,
  RefreshCw,
  Search,
  Filter,
  FileText,
  ShoppingCart,
} from "lucide-react";
import { motion } from "framer-motion";
import { NovaOrdemModal } from "@/components/ferramentas/ativos/modals/NovaOrdemModal";
import { PostingDetailsModal } from "@/components/ferramentas/ativos/modals/PostingDetailsModal";
import { toast } from "@/components/ui/use-toast";
import { getPostages, updatePostageStatus, getTifluxTicketsForExpedicao } from "@/services/carrierAgentcore";
import type { SGAPostage, TifluxTicket } from "@/lib/ativos/types";

/**
 * Expedição Page - Shipping Orders Management
 *
 * Tab-based view (same as Reversa):
 * - Pendentes: Tiflux tickets (stage: Enviado/Enviar Logistica)
 * - Em Andamento: Postages with status 'aguardando' or 'em_transito'
 * - Concluídas: Postages with status 'entregue'
 */

// Types for shipping orders
export type ShippingOrderStatus = "aguardando" | "em_transito" | "entregue" | "cancelado";

export type ShippingOrderItem = {
  ativoId: string;
  ativoCodigo: string;
  ativoNome: string;
  quantidade: number;
};

export type ShippingOrder = {
  id: string;
  codigo: string;
  cliente: string;
  destino: { nome: string; cep?: string };
  status: ShippingOrderStatus;
  prioridade: string;
  responsavel: { nome: string };
  itens: ShippingOrderItem[];
  dataCriacao: string;
  dataPrevista: string;
  carrier?: string;
  trackingCode?: string;
  price?: number;
  // Tiflux ticket context (BUG-040)
  tifluxTicketNumber?: string;
  tifluxTicketTitle?: string;
};

// Query keys
const POSTAGES_QUERY_KEY = ["postages"];
const TIFLUX_TICKETS_QUERY_KEY = ["tiflux-tickets-expedicao"];

/**
 * Transform SGAPostage from API to ShippingOrder for UI
 */
function transformPostageToOrder(posting: SGAPostage): ShippingOrder {
  return {
    id: posting.posting_id,
    codigo: posting.order_code,
    cliente: posting.destination.name,
    destino: {
      nome: posting.destination.name,
      cep: posting.destination.cep,
    },
    status: posting.status,
    prioridade: (posting.urgency || "normal").toLowerCase(),
    responsavel: { nome: "Usuario" },
    itens: [],
    dataCriacao: posting.created_at,
    dataPrevista: posting.estimated_delivery,
    carrier: posting.carrier,
    trackingCode: posting.tracking_code,
    price: posting.price,
    // Tiflux ticket context (BUG-040)
    tifluxTicketNumber: posting.tiflux_ticket_number,
    tifluxTicketTitle: posting.tiflux_ticket_title,
  };
}

export default function ExpedicaoPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>("pendentes");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<ShippingOrder | null>(null);
  const [selectedTicket, setSelectedTicket] = useState<TifluxTicket | null>(null);

  // Fetch Tiflux tickets for "Pendentes" tab
  const {
    data: tifluxData,
    isLoading: tifluxLoading,
    refetch: refetchTiflux,
  } = useQuery({
    queryKey: TIFLUX_TICKETS_QUERY_KEY,
    queryFn: async () => {
      const response = await getTifluxTicketsForExpedicao();
      return response.data;
    },
  });

  // Fetch postages for "Em Andamento" and "Concluídas" tabs
  const {
    data: postagesData,
    isLoading: postagesLoading,
    refetch: refetchPostages,
  } = useQuery({
    queryKey: POSTAGES_QUERY_KEY,
    queryFn: async () => {
      const response = await getPostages();
      if (response.data.success) {
        return response.data.postings.map(transformPostageToOrder);
      }
      return [];
    },
  });

  // Mutation for updating postage status
  const updateStatusMutation = useMutation({
    mutationFn: async ({ postingId, newStatus }: { postingId: string; newStatus: string }) => {
      const response = await updatePostageStatus(postingId, newStatus);
      if (!response.data.success) {
        throw new Error(response.data.error || "Failed to update status");
      }
      return response.data.posting;
    },
    onSuccess: (updatedPosting, { newStatus }) => {
      queryClient.invalidateQueries({ queryKey: POSTAGES_QUERY_KEY });
      const statusLabel = newStatus === "em_transito" ? "Em Transito" : "Entregue";
      toast({
        title: `Status atualizado para "${statusLabel}"`,
        description: `Pedido: ${updatedPosting.order_code}`,
      });
    },
    onError: (error) => {
      toast({
        title: "Erro ao atualizar status",
        description: error instanceof Error ? error.message : "Tente novamente",
        variant: "destructive",
      });
    },
  });

  // Filter tickets by search
  const filterTicketsBySearch = (tickets: TifluxTicket[]): TifluxTicket[] => {
    if (!searchQuery.trim()) return tickets;
    const lowerQuery = searchQuery.toLowerCase();
    return tickets.filter((ticket) => (
      String(ticket.ticket_number).includes(lowerQuery) ||
      ticket.client_name?.toLowerCase().includes(lowerQuery) ||
      ticket.stage?.toLowerCase().includes(lowerQuery)
    ));
  };

  // Filter postages by search
  const filterPostagesBySearch = (postages: ShippingOrder[]): ShippingOrder[] => {
    if (!searchQuery.trim()) return postages;
    const lowerQuery = searchQuery.toLowerCase();
    return postages.filter((order) => (
      order.codigo?.toLowerCase().includes(lowerQuery) ||
      order.cliente?.toLowerCase().includes(lowerQuery) ||
      order.trackingCode?.toLowerCase().includes(lowerQuery)
    ));
  };

  // Filtered data
  const ticketsPendentes = filterTicketsBySearch(tifluxData?.tickets || []);
  const postagesEmAndamento = filterPostagesBySearch(
    (postagesData || []).filter((o) => o.status === "aguardando" || o.status === "em_transito")
  );
  const postagesConcluidas = filterPostagesBySearch(
    (postagesData || []).filter((o) => o.status === "entregue")
  );

  // Handle ticket click - open modal
  const handleTicketClick = useCallback((ticket: TifluxTicket) => {
    setSelectedTicket(ticket);
    setIsModalOpen(true);
  }, []);

  // Handle postage click
  const handlePostageClick = useCallback((order: ShippingOrder) => {
    setSelectedOrder(order);
  }, []);

  // Handle new order created from modal
  const handleOrderCreated = useCallback((order: ShippingOrder) => {
    queryClient.invalidateQueries({ queryKey: POSTAGES_QUERY_KEY });
    queryClient.invalidateQueries({ queryKey: TIFLUX_TICKETS_QUERY_KEY });
    setSelectedTicket(null);
    toast({
      title: "Postagem criada com sucesso!",
      description: `Codigo: ${order.codigo}${order.trackingCode ? ` | Rastreio: ${order.trackingCode}` : ""}`,
    });
  }, [queryClient]);

  // Move order to next status
  const moveToNextStatus = useCallback((orderId: string, currentStatus: ShippingOrderStatus) => {
    const nextStatus: Record<ShippingOrderStatus, ShippingOrderStatus> = {
      aguardando: "em_transito",
      em_transito: "entregue",
      entregue: "entregue",
      cancelado: "cancelado",
    };

    const newStatus = nextStatus[currentStatus];
    if (newStatus !== currentStatus) {
      updateStatusMutation.mutate({ postingId: orderId, newStatus });
    }
  }, [updateStatusMutation]);

  // Handle refresh
  const handleRefresh = () => {
    if (activeTab === "pendentes") {
      refetchTiflux();
    } else {
      refetchPostages();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <AssetManagementHeader
        title="Expedicao"
        subtitle="Gerencie ordens de envio e entregas"
        primaryAction={{
          label: "Atualizar",
          onClick: handleRefresh,
          icon: <RefreshCw className="w-4 h-4" />,
        }}
        secondaryActions={[
          {
            label: "Transportadoras",
            href: "/ferramentas/ativos/transportadoras",
            icon: <Truck className="w-4 h-4" />,
          },
        ]}
      />

      {/* Search Bar */}
      <GlassCard className="p-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              placeholder="Buscar por ticket, cliente ou codigo..."
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
            <TabsTrigger value="pendentes" className="data-[state=active]:bg-orange-500/20">
              Pendentes
              {ticketsPendentes.length > 0 && (
                <Badge variant="outline" className="ml-2">
                  {ticketsPendentes.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="andamento" className="data-[state=active]:bg-blue-500/20">
              Em Andamento
              {postagesEmAndamento.length > 0 && (
                <Badge variant="outline" className="ml-2">
                  {postagesEmAndamento.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="concluidas" className="data-[state=active]:bg-green-500/20">
              Concluidas
              {postagesConcluidas.length > 0 && (
                <Badge variant="outline" className="ml-2">
                  {postagesConcluidas.length}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Pendentes Tab - Tiflux Tickets */}
          <TabsContent value="pendentes" className="mt-6">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-orange-400" />
                  <GlassCardTitle>Tickets Pendentes</GlassCardTitle>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchTiflux()}
                  disabled={tifluxLoading}
                  className="border-border"
                >
                  <RefreshCw className={`w-4 h-4 ${tifluxLoading ? "animate-spin" : ""}`} />
                </Button>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              {tifluxLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
                </div>
              ) : ticketsPendentes.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {ticketsPendentes.map((ticket: TifluxTicket, index: number) => (
                    <motion.div
                      key={ticket.ticket_number}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors"
                    >
                      {/* Ticket Number + Stage Badge */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold text-orange-400">
                          #{ticket.ticket_number}
                        </p>
                        <Badge variant="outline" className="text-xs">
                          {ticket.stage}
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

                      {/* Title/Description */}
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

                        {/* Date */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <Calendar className="w-3 h-3 shrink-0" />
                          <span>
                            {new Date(ticket.created_at).toLocaleDateString("pt-BR")}
                          </span>
                        </div>
                      </div>

                      {/* Realizar Cotacao Button */}
                      <Button
                        variant="default"
                        size="sm"
                        className="w-full mt-4 bg-blue-600 hover:bg-blue-700 text-white"
                        onClick={() => handleTicketClick(ticket)}
                      >
                        <ShoppingCart className="w-4 h-4 mr-2" />
                        Realizar Cotacao
                      </Button>
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
                    Tickets do Tiflux com estagio &quot;Enviado/Enviar Logistica&quot; aparecerao aqui
                  </p>
                </div>
              )}
            </GlassCardContent>
          </TabsContent>

          {/* Em Andamento Tab - Postages */}
          <TabsContent value="andamento" className="mt-6">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-blue-400" />
                  <GlassCardTitle>Postagens em Andamento</GlassCardTitle>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchPostages()}
                  disabled={postagesLoading}
                  className="border-border"
                >
                  <RefreshCw className={`w-4 h-4 ${postagesLoading ? "animate-spin" : ""}`} />
                </Button>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              {postagesLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
                </div>
              ) : postagesEmAndamento.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {postagesEmAndamento.map((order: ShippingOrder, index: number) => (
                    <motion.div
                      key={order.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => handlePostageClick(order)}
                      className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      {/* Ticket/Order Info + Status Badge */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold text-blue-400">
                          {order.tifluxTicketNumber ? `#${order.tifluxTicketNumber}` : order.codigo}
                        </p>
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            order.status === "em_transito"
                              ? "bg-blue-500/20 text-blue-400"
                              : "bg-yellow-500/20 text-yellow-400"
                          }`}
                        >
                          {order.status === "em_transito" ? "Em Transito" : "Aguardando"}
                        </Badge>
                      </div>

                      {/* Tiflux Ticket Title or Client */}
                      <p className="text-sm font-medium text-text-primary truncate mb-1" title={order.tifluxTicketTitle || order.cliente}>
                        {(order.tifluxTicketTitle || order.cliente).length > 35
                          ? `${(order.tifluxTicketTitle || order.cliente).substring(0, 35)}...`
                          : (order.tifluxTicketTitle || order.cliente)}
                      </p>

                      {/* Carrier + Price */}
                      <div className="flex items-center gap-2 text-xs text-text-muted mb-3">
                        <Truck className="w-3 h-3 shrink-0" />
                        <span>{order.carrier || "Correios"} - R$ {order.price?.toFixed(2) || "0.00"}</span>
                      </div>

                      <div className="border-t border-border/50 pt-3 mt-2 space-y-2">
                        {/* Destination */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <MapPin className="w-3 h-3 shrink-0" />
                          <span className="truncate">{order.destino.nome}</span>
                        </div>

                        {/* Tracking Code */}
                        {order.trackingCode && (
                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <Package className="w-3 h-3 shrink-0" />
                            <span className="font-mono">{order.trackingCode}</span>
                          </div>
                        )}

                        {/* Date */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <Calendar className="w-3 h-3 shrink-0" />
                          <span>
                            {order.dataPrevista && order.dataPrevista !== ""
                              ? new Date(order.dataPrevista).toLocaleDateString("pt-BR")
                              : order.dataCriacao
                                ? new Date(order.dataCriacao).toLocaleDateString("pt-BR")
                                : "—"}
                          </span>
                        </div>
                      </div>

                      {/* Action Button */}
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full mt-4 border-border"
                        onClick={(e) => {
                          e.stopPropagation();
                          moveToNextStatus(order.id, order.status);
                        }}
                        disabled={updateStatusMutation.isPending}
                      >
                        {updateStatusMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : order.status === "aguardando" ? (
                          <>
                            <Truck className="w-4 h-4 mr-2" />
                            Marcar Em Transito
                          </>
                        ) : (
                          <>
                            <CheckCircle className="w-4 h-4 mr-2" />
                            Marcar Entregue
                          </>
                        )}
                      </Button>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <InboxIcon className="w-12 h-12 text-text-muted mb-3" />
                  <p className="text-sm font-medium text-text-primary mb-1">
                    Nenhuma postagem em andamento
                  </p>
                  <p className="text-xs text-text-muted">
                    Postagens criadas e em transito aparecerao aqui
                  </p>
                </div>
              )}
            </GlassCardContent>
          </TabsContent>

          {/* Concluídas Tab - Delivered Postages */}
          <TabsContent value="concluidas" className="mt-6">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-400" />
                  <GlassCardTitle>Postagens Concluidas</GlassCardTitle>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchPostages()}
                  disabled={postagesLoading}
                  className="border-border"
                >
                  <RefreshCw className={`w-4 h-4 ${postagesLoading ? "animate-spin" : ""}`} />
                </Button>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              {postagesLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 text-green-400 animate-spin" />
                </div>
              ) : postagesConcluidas.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {postagesConcluidas.map((order: ShippingOrder, index: number) => (
                    <motion.div
                      key={order.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      onClick={() => handlePostageClick(order)}
                      className="bg-white/5 border border-border rounded-lg p-4 hover:bg-white/10 transition-colors cursor-pointer"
                    >
                      {/* Ticket/Order Info + Status Badge */}
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold text-green-400">
                          {order.tifluxTicketNumber ? `#${order.tifluxTicketNumber}` : order.codigo}
                        </p>
                        <Badge variant="outline" className="text-xs bg-green-500/20 text-green-400">
                          Entregue
                        </Badge>
                      </div>

                      {/* Tiflux Ticket Title or Client */}
                      <p className="text-sm font-medium text-text-primary truncate mb-1" title={order.tifluxTicketTitle || order.cliente}>
                        {(order.tifluxTicketTitle || order.cliente).length > 35
                          ? `${(order.tifluxTicketTitle || order.cliente).substring(0, 35)}...`
                          : (order.tifluxTicketTitle || order.cliente)}
                      </p>

                      {/* Carrier + Price */}
                      <div className="flex items-center gap-2 text-xs text-text-muted mb-3">
                        <Truck className="w-3 h-3 shrink-0" />
                        <span>{order.carrier || "Correios"} - R$ {order.price?.toFixed(2) || "0.00"}</span>
                      </div>

                      <div className="border-t border-border/50 pt-3 mt-2 space-y-2">
                        {/* Destination */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <MapPin className="w-3 h-3 shrink-0" />
                          <span className="truncate">{order.destino.nome}</span>
                        </div>

                        {/* Tracking Code */}
                        {order.trackingCode && (
                          <div className="flex items-center gap-2 text-xs text-text-muted">
                            <Package className="w-3 h-3 shrink-0" />
                            <span className="font-mono">{order.trackingCode}</span>
                          </div>
                        )}

                        {/* Delivery Date */}
                        <div className="flex items-center gap-2 text-xs text-text-muted">
                          <Calendar className="w-3 h-3 shrink-0" />
                          <span>
                            Entregue em {order.dataPrevista && order.dataPrevista !== ""
                              ? new Date(order.dataPrevista).toLocaleDateString("pt-BR")
                              : new Date(order.dataCriacao).toLocaleDateString("pt-BR")}
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
                    Nenhuma postagem concluida
                  </p>
                  <p className="text-xs text-text-muted">
                    Postagens entregues aparecerao aqui
                  </p>
                </div>
              )}
            </GlassCardContent>
          </TabsContent>
        </Tabs>
      </GlassCard>

      {/* Nova Ordem Modal */}
      <NovaOrdemModal
        open={isModalOpen}
        onOpenChange={(open) => {
          setIsModalOpen(open);
          if (!open) setSelectedTicket(null);
        }}
        onOrderCreated={handleOrderCreated}
        tifluxTicket={selectedTicket}
      />

      {/* Order Details Modal */}
      <PostingDetailsModal
        order={selectedOrder}
        onClose={() => setSelectedOrder(null)}
        onMoveToNextStatus={moveToNextStatus}
        isUpdating={updateStatusMutation.isPending}
      />
    </div>
  );
}
