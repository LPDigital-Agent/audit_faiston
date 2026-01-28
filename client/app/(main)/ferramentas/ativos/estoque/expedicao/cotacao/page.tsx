'use client';

// =============================================================================
// Cotação de Frete Page - SGA Inventory Module (CarrierAgent)
// =============================================================================
// Unified carrier quote comparison with AI recommendations.
// Supports Correios, Loggi, Gollog, and local transportadoras.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Truck,
  ArrowLeft,
  Search,
  Package,
  Timer,
  DollarSign,
  RefreshCw,
  AlertTriangle,
  Star,
  Plane,
  Car,
  Zap,
} from 'lucide-react';
import { getShippingQuotes, trackShipment } from '@/services/carrierAgentcore';
import type {
  SGAShippingQuote,
  SGACarrierRecommendation,
  SGAExpeditionUrgency,
  SGATrackingEvent,
} from '@/lib/ativos/types';

// =============================================================================
// Constants
// =============================================================================

const URGENCY_OPTIONS: { value: SGAExpeditionUrgency; label: string; color: string }[] = [
  { value: 'LOW', label: 'Econômico', color: 'bg-gray-500' },
  { value: 'NORMAL', label: 'Normal', color: 'bg-blue-500' },
  { value: 'HIGH', label: 'Expresso', color: 'bg-yellow-500' },
  { value: 'URGENT', label: 'Urgente', color: 'bg-red-500' },
];

const CARRIER_ICONS: Record<string, React.ReactNode> = {
  CORREIOS: <Package className="w-4 h-4" />,
  LOGGI: <Zap className="w-4 h-4" />,
  GOLLOG: <Plane className="w-4 h-4" />,
  TRANSPORTADORA: <Truck className="w-4 h-4" />,
  DEDICADO: <Car className="w-4 h-4" />,
};

// =============================================================================
// Page Component
// =============================================================================

export default function CotacaoPage() {
  // Quote form state
  const [originCep, setOriginCep] = useState('04548-005'); // Faiston HQ
  const [destinationCep, setDestinationCep] = useState('');
  const [weightKg, setWeightKg] = useState(1);
  const [length, setLength] = useState(30);
  const [width, setWidth] = useState(20);
  const [height, setHeight] = useState(10);
  const [value, setValue] = useState(500);
  const [urgency, setUrgency] = useState<SGAExpeditionUrgency>('NORMAL');

  // Tracking form state
  const [trackingCode, setTrackingCode] = useState('');

  // Results state
  const [quotes, setQuotes] = useState<SGAShippingQuote[]>([]);
  const [recommendation, setRecommendation] = useState<SGACarrierRecommendation | null>(null);
  const [trackingEvents, setTrackingEvents] = useState<SGATrackingEvent[]>([]);
  const [trackingStatus, setTrackingStatus] = useState<string | null>(null);

  // Get quotes mutation
  const quotesMutation = useMutation({
    mutationFn: async () => {
      const result = await getShippingQuotes({
        origin_cep: originCep,
        destination_cep: destinationCep,
        weight_kg: weightKg,
        dimensions: { length, width, height },
        value,
        urgency,
      });
      return result.data;
    },
    onSuccess: (data) => {
      setQuotes(data.quotes || []);
      setRecommendation(data.recommendation || null);
    },
  });

  // Track shipment mutation
  const trackMutation = useMutation({
    mutationFn: async () => {
      const result = await trackShipment({ tracking_code: trackingCode });
      return result.data;
    },
    onSuccess: (data) => {
      if (data.tracking) {
        setTrackingEvents(data.tracking.events || []);
        setTrackingStatus(data.tracking.status);
      }
    },
  });

  const handleGetQuotes = () => {
    if (!destinationCep) return;
    quotesMutation.mutate();
  };

  const handleTrack = () => {
    if (!trackingCode) return;
    trackMutation.mutate();
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/expedicao">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Expedição
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-green-400" />
            Cotação de Frete
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Compare preços de transportadoras com recomendação AI
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Quote Form */}
        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle>Calcular Frete</GlassCardTitle>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-4">
              {/* CEPs */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    CEP Origem
                  </label>
                  <Input
                    placeholder="00000-000"
                    value={originCep}
                    onChange={(e) => setOriginCep(e.target.value)}
                    className="bg-white/5 border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    CEP Destino *
                  </label>
                  <Input
                    placeholder="00000-000"
                    value={destinationCep}
                    onChange={(e) => setDestinationCep(e.target.value)}
                    className="bg-white/5 border-border"
                  />
                </div>
              </div>

              {/* Weight & Dimensions */}
              <div className="grid grid-cols-4 gap-3">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Peso (kg)
                  </label>
                  <Input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={weightKg}
                    onChange={(e) => setWeightKg(parseFloat(e.target.value) || 1)}
                    className="bg-white/5 border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    C (cm)
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={length}
                    onChange={(e) => setLength(parseInt(e.target.value) || 1)}
                    className="bg-white/5 border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    L (cm)
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={width}
                    onChange={(e) => setWidth(parseInt(e.target.value) || 1)}
                    className="bg-white/5 border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    A (cm)
                  </label>
                  <Input
                    type="number"
                    min={1}
                    value={height}
                    onChange={(e) => setHeight(parseInt(e.target.value) || 1)}
                    className="bg-white/5 border-border"
                  />
                </div>
              </div>

              {/* Value & Urgency */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Valor Declarado (R$)
                  </label>
                  <Input
                    type="number"
                    min={0}
                    value={value}
                    onChange={(e) => setValue(parseFloat(e.target.value) || 0)}
                    className="bg-white/5 border-border"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Urgência
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={urgency}
                    onChange={(e) => setUrgency(e.target.value as SGAExpeditionUrgency)}
                  >
                    {URGENCY_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Error */}
              {quotesMutation.error && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <p className="text-sm text-red-400">{quotesMutation.error.message}</p>
                </div>
              )}

              {/* Submit */}
              <Button
                className="w-full"
                disabled={!destinationCep || quotesMutation.isPending}
                onClick={handleGetQuotes}
              >
                {quotesMutation.isPending ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Consultando...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 mr-2" />
                    Buscar Cotações
                  </>
                )}
              </Button>
            </div>
          </GlassCardContent>
        </GlassCard>

        {/* Tracking */}
        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle>Rastrear Envio</GlassCardTitle>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Código de Rastreio
                </label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Ex: AA123456789BR"
                    value={trackingCode}
                    onChange={(e) => setTrackingCode(e.target.value)}
                    className="bg-white/5 border-border flex-1"
                  />
                  <Button
                    disabled={!trackingCode || trackMutation.isPending}
                    onClick={handleTrack}
                  >
                    {trackMutation.isPending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Search className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>

              {/* Tracking Results */}
              {trackingStatus && (
                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <p className="text-sm font-medium text-blue-400 mb-2">
                    Status: {trackingStatus}
                  </p>
                  <div className="space-y-2">
                    {trackingEvents.map((event, idx) => (
                      <div key={idx} className="text-xs text-text-muted">
                        <p>{event.date} - {event.location}</p>
                        <p className="text-text-primary">{event.status}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {trackMutation.error && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <p className="text-sm text-red-400">{trackMutation.error.message}</p>
                </div>
              )}

              {/* Note about mock data */}
              <p className="text-xs text-text-muted italic">
                Nota: Rastreamento em tempo real requer integração com APIs das transportadoras.
              </p>
            </div>
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* Quote Results */}
      {quotes.length > 0 && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between">
              <GlassCardTitle>Cotações Disponíveis</GlassCardTitle>
              {recommendation && (
                <Badge variant="outline" className="text-green-400 border-green-400">
                  <Star className="w-3 h-3 mr-1" />
                  Recomendado: {recommendation.carrier}
                </Badge>
              )}
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            {/* AI Recommendation */}
            {recommendation && (
              <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg mb-6">
                <div className="flex items-center gap-2 mb-2">
                  <Star className="w-5 h-5 text-green-400" />
                  <p className="text-sm font-medium text-green-400">
                    Recomendação NEXO AI
                  </p>
                </div>
                <p className="text-sm text-text-primary mb-2">
                  <strong>{recommendation.carrier}</strong> - {recommendation.modal}
                </p>
                <p className="text-xs text-text-muted">{recommendation.reason}</p>
                {recommendation.price && (
                  <p className="text-lg font-bold text-green-400 mt-2">
                    R$ {recommendation.price.toFixed(2)}
                  </p>
                )}
              </div>
            )}

            {/* All Quotes Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {quotes.map((quote, index) => (
                <div
                  key={index}
                  className={`p-4 border rounded-lg transition-all ${
                    quote.available
                      ? 'bg-white/5 border-border hover:border-blue-500/50'
                      : 'bg-white/2 border-border/50 opacity-50'
                  } ${
                    recommendation?.carrier === quote.carrier &&
                    recommendation?.modal === quote.modal
                      ? 'border-green-500/50 bg-green-500/5'
                      : ''
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    {CARRIER_ICONS[quote.carrier_type] || <Truck className="w-4 h-4" />}
                    <span className="font-medium text-text-primary">{quote.carrier}</span>
                  </div>

                  <Badge variant="outline" className="mb-2">
                    {quote.modal}
                  </Badge>

                  {quote.available ? (
                    <>
                      <p className="text-xl font-bold text-text-primary mt-2">
                        R$ {quote.price.toFixed(2)}
                      </p>
                      <div className="flex items-center gap-1 text-xs text-text-muted mt-1">
                        <Timer className="w-3 h-3" />
                        {quote.delivery_days} dia{quote.delivery_days > 1 ? 's' : ''} úteis
                      </div>
                      <p className="text-xs text-text-muted mt-1">
                        Até {quote.delivery_date}
                      </p>
                      <p className="text-xs text-text-muted mt-2">
                        Limite: {quote.weight_limit}kg / {quote.dimensions_limit}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-red-400 mt-2">
                      {quote.reason || 'Indisponível'}
                    </p>
                  )}
                </div>
              ))}
            </div>

            {/* Note about mock data */}
            <p className="text-xs text-text-muted italic mt-4">
              Nota: Cotações simuladas. Integração com APIs de transportadoras pendente.
            </p>
          </GlassCardContent>
        </GlassCard>
      )}
    </div>
  );
}
