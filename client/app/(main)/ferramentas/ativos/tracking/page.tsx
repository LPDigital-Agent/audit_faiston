"use client";

// =============================================================================
// Tracking Page - Real-time Asset and Vehicle Tracking
// =============================================================================
// Displays map view with active shipments and vehicle locations.
// Mock data for demonstration - click on a delivery to see its location on map.
// =============================================================================

import { useState } from "react";
import dynamic from "next/dynamic";
import { GlassCard, GlassCardHeader, GlassCardTitle } from "@/components/shared/glass-card";
import { AssetManagementHeader } from "@/components/ferramentas/ativos/asset-management-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  MapPin,
  Search,
  Truck,
  Navigation,
  Clock,
  Package,
  RefreshCcw,
  Maximize2,
  Signal,
  Battery,
  InboxIcon,
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

// Dynamic import for Leaflet (SSR disabled - Leaflet requires window)
const TrackingMap = dynamic(
  () => import("@/components/ferramentas/ativos/tracking/TrackingMap"),
  { ssr: false, loading: () => <MapPlaceholder /> }
);

// Map placeholder while loading
function MapPlaceholder() {
  return (
    <div className="absolute inset-0 mt-14 flex items-center justify-center bg-gradient-to-br from-blue-dark/20 to-magenta-dark/20">
      <div className="text-center">
        <MapPin className="w-16 h-16 mx-auto mb-4 text-text-muted opacity-50 animate-pulse" />
        <p className="text-text-muted">Carregando mapa...</p>
      </div>
    </div>
  );
}

// =============================================================================
// Types
// =============================================================================

type Vehicle = {
  id: string;
  placa: string;
  motorista: string;
  status: string;
  ultimaAtualizacao: string;
  bateria: number;
  sinal: string;
  destino: string;
  etaMinutos: number;
};

export type MockDelivery = {
  id: string;
  codigo: string;
  destino: string;
  lat: number;
  lng: number;
  status: "em_transito" | "entregue" | "pendente";
  previsao: string;
  cliente: string;
  endereco: string;
};

// =============================================================================
// Mock Data - 3 Example Deliveries
// =============================================================================

const mockDeliveries: MockDelivery[] = [
  {
    id: "ENT-001",
    codigo: "EXP-2024-0142",
    destino: "Sao Paulo - SP",
    lat: -23.5505,
    lng: -46.6333,
    status: "em_transito",
    previsao: "2024-01-24",
    cliente: "Tech Solutions Ltda",
    endereco: "Av. Paulista, 1000 - Bela Vista",
  },
  {
    id: "ENT-002",
    codigo: "EXP-2024-0143",
    destino: "Rio de Janeiro - RJ",
    lat: -22.9068,
    lng: -43.1729,
    status: "em_transito",
    previsao: "2024-01-25",
    cliente: "Innovate Corp",
    endereco: "Rua do Ouvidor, 50 - Centro",
  },
  {
    id: "ENT-003",
    codigo: "EXP-2024-0144",
    destino: "Belo Horizonte - MG",
    lat: -19.9167,
    lng: -43.9345,
    status: "em_transito",
    previsao: "2024-01-26",
    cliente: "Mining Systems SA",
    endereco: "Av. Afonso Pena, 1500 - Centro",
  },
];

// =============================================================================
// Status Labels
// =============================================================================

const statusLabels: Record<string, { label: string; color: string }> = {
  em_rota: { label: "Em Rota", color: "bg-green-500/20 text-green-400" },
  parado: { label: "Parado", color: "bg-yellow-500/20 text-yellow-400" },
  offline: { label: "Offline", color: "bg-red-500/20 text-red-400" },
};

const signalLabels: Record<string, { label: string; color: string }> = {
  forte: { label: "Forte", color: "text-green-400" },
  medio: { label: "Medio", color: "text-yellow-400" },
  fraco: { label: "Fraco", color: "text-red-400" },
};

// =============================================================================
// Component
// =============================================================================

export default function TrackingPage() {
  const [selectedDelivery, setSelectedDelivery] = useState<MockDelivery | null>(null);

  // Real data - empty until backend integration
  const vehicles: Vehicle[] = [];

  const handleDeliveryClick = (delivery: MockDelivery) => {
    setSelectedDelivery(delivery);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <AssetManagementHeader
        title="Tracking e Logistica"
        subtitle="Rastreamento em tempo real de veiculos e entregas"
        secondaryActions={[
          {
            label: "Atualizar",
            onClick: () => console.log("Atualizar"),
            icon: <RefreshCcw className="w-4 h-4" />,
          },
        ]}
      />

      {/* Map + Vehicle List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map Area */}
        <div className="lg:col-span-2">
          <GlassCard className="h-[500px] relative overflow-hidden">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-blue-light" />
                  <GlassCardTitle>Mapa de Rastreamento</GlassCardTitle>
                </div>
                <Button variant="ghost" size="sm">
                  <Maximize2 className="w-4 h-4" />
                </Button>
              </div>
            </GlassCardHeader>

            {/* Leaflet Map */}
            <div className="absolute inset-0 mt-14">
              <TrackingMap
                deliveries={mockDeliveries}
                selectedDelivery={selectedDelivery}
                onDeliverySelect={setSelectedDelivery}
              />
            </div>
          </GlassCard>
        </div>

        {/* Vehicle List */}
        <div className="lg:col-span-1">
          <GlassCard className="h-[500px] flex flex-col">
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-magenta-light" />
                  <GlassCardTitle>Veiculos</GlassCardTitle>
                </div>
                <Badge variant="outline" className="text-xs">
                  {vehicles.length} ativos
                </Badge>
              </div>
            </GlassCardHeader>

            {/* Search */}
            <div className="px-4 pb-3">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <Input
                  placeholder="Buscar veiculo..."
                  className="pl-10 bg-white/5 border-border h-9 text-sm"
                />
              </div>
            </div>

            <ScrollArea className="flex-1">
              <div className="space-y-2 px-4 pb-4">
                {vehicles.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <InboxIcon className="w-10 h-10 text-text-muted mb-3" />
                    <p className="text-sm font-medium text-text-primary mb-1">
                      Nenhum veiculo
                    </p>
                    <p className="text-xs text-text-muted">
                      Os veiculos rastreados aparecerao aqui
                    </p>
                  </div>
                ) : (
                  vehicles.map((vehicle, index) => {
                    const status = statusLabels[vehicle.status] || statusLabels.offline;
                    const sinal = signalLabels[vehicle.sinal] || signalLabels.fraco;

                    return (
                      <motion.div
                        key={vehicle.id}
                        initial={{ opacity: 0, x: 10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors cursor-pointer border border-border"
                      >
                        {/* Header */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${status.color.replace("text-", "bg-").replace("400", "500/20")}`}>
                              <Truck className={`w-4 h-4 ${status.color.split(" ")[1]}`} />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-text-primary">{vehicle.placa}</p>
                              <p className="text-xs text-text-muted">{vehicle.motorista}</p>
                            </div>
                          </div>
                          <Badge className={status.color}>{status.label}</Badge>
                        </div>

                        {/* Destination */}
                        <div className="flex items-center gap-1 text-xs text-text-muted mb-2">
                          <Navigation className="w-3 h-3" />
                          <span className="truncate">{vehicle.destino}</span>
                        </div>

                        {/* Stats */}
                        <div className="flex items-center justify-between text-xs text-text-muted pt-2 border-t border-border">
                          <div className="flex items-center gap-3">
                            <div className="flex items-center gap-1">
                              <Battery className="w-3 h-3" />
                              <span>{vehicle.bateria}%</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Signal className={`w-3 h-3 ${sinal.color}`} />
                              <span className={sinal.color}>{sinal.label}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            <span>{vehicle.etaMinutos} min</span>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </ScrollArea>
          </GlassCard>
        </div>
      </div>

      {/* Active Shipments - Mock Data */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-blue-light" />
              <GlassCardTitle>Entregas em Andamento</GlassCardTitle>
            </div>
            <Badge variant="outline">{mockDeliveries.length} entregas</Badge>
          </div>
        </GlassCardHeader>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
          {mockDeliveries.map((delivery, index) => (
            <motion.div
              key={delivery.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              onClick={() => handleDeliveryClick(delivery)}
              className={cn(
                "p-4 rounded-lg bg-white/5 border cursor-pointer transition-all",
                selectedDelivery?.id === delivery.id
                  ? "border-blue-500 bg-blue-500/10 ring-1 ring-blue-500/50"
                  : "border-border hover:bg-white/10 hover:border-blue-500/50"
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-medium text-text-primary">{delivery.codigo}</p>
                <Badge className="bg-blue-500/20 text-blue-400">Em Transito</Badge>
              </div>

              <p className="text-sm text-text-primary mb-1">{delivery.cliente}</p>

              <div className="flex items-center gap-2 text-xs text-text-muted mb-2">
                <MapPin className="w-3 h-3" />
                <span className="truncate">{delivery.destino}</span>
              </div>

              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Clock className="w-3 h-3" />
                <span>Previsao: {new Date(delivery.previsao).toLocaleDateString("pt-BR")}</span>
              </div>

              {selectedDelivery?.id === delivery.id && (
                <div className="mt-3 pt-3 border-t border-blue-500/30">
                  <p className="text-xs text-blue-400">Visualizando no mapa</p>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
