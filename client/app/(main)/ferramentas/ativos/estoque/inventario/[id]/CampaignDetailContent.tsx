'use client';

// =============================================================================
// Campaign Detail Content - SGA Inventory Module
// =============================================================================
// Single campaign view with counting session, divergences, and adjustments.
// Client component for dynamic rendering.
// =============================================================================

import { useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  ClipboardCheck,
  ArrowLeft,
  Play,
  Pause,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  Package,
  MapPin,
  AlertTriangle,
  CheckCircle2,
  Camera,
  Plus,
  Minus,
} from 'lucide-react';
import { useInventoryCount } from '@/hooks/ativos';
import {
  CAMPAIGN_STATUS_LABELS,
  CAMPAIGN_STATUS_COLORS,
  DIVERGENCE_TYPE_LABELS,
  DIVERGENCE_TYPE_COLORS,
} from '@/lib/ativos/constants';

// =============================================================================
// Component
// =============================================================================

interface CampaignDetailContentProps {
  id: string;
}

export function CampaignDetailContent({ id }: CampaignDetailContentProps) {
  const {
    campaigns,
    campaignsLoading,
    activeCampaign,
    countingItems,
    currentItem,
    currentItemIndex,
    countingProgress,
    isCountingSessionActive,
    divergences,
    selectCampaign,
    startCountingSession,
    endCountingSession,
    submitCountResult,
    goToNextItem,
    goToPreviousItem,
    addScannedSerial,
    scannedSerials,
    clearScannedSerials,
  } = useInventoryCount();

  const [countedQuantity, setCountedQuantity] = useState(0);
  const [serialInput, setSerialInput] = useState('');
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Find campaign from list
  const campaign = campaigns.find(c => c.id === id);

  // Auto-select campaign if not already
  if (campaign && activeCampaign?.id !== id) {
    selectCampaign(campaign);
  }

  // Handle serial scan
  const handleAddSerial = () => {
    if (serialInput.trim()) {
      addScannedSerial(serialInput.trim());
      setSerialInput('');
    }
  };

  // Handle count submit
  const handleSubmitCount = async () => {
    if (!currentItem) return;

    setIsSubmitting(true);
    try {
      await submitCountResult({
        part_number: currentItem.partNumber,
        location_id: currentItem.locationId,
        counted_quantity: countedQuantity,
        serial_numbers_found: scannedSerials.length > 0 ? scannedSerials : undefined,
        notes: notes || undefined,
      });

      // Reset for next item
      setCountedQuantity(0);
      setNotes('');
      clearScannedSerials();
      goToNextItem();
    } catch (error) {
      console.error('Error submitting count:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (campaignsLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
        <ClipboardCheck className="w-16 h-16 text-text-muted mb-4" />
        <h2 className="text-lg font-semibold text-text-primary mb-2">
          Campanha nao encontrada
        </h2>
        <p className="text-sm text-text-muted mb-4">
          A campanha solicitada nao existe ou foi removida.
        </p>
        <Button asChild>
          <Link href="/ferramentas/ativos/estoque/inventario">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Voltar a lista
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/inventario">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Inventario
              </Link>
            </Button>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-text-primary">
              {campaign.name}
            </h1>
            <Badge className={CAMPAIGN_STATUS_COLORS[campaign.status] || 'bg-gray-500/20'}>
              {CAMPAIGN_STATUS_LABELS[campaign.status] || campaign.status}
            </Badge>
          </div>
          {campaign.description && (
            <p className="text-sm text-text-muted mt-1">
              {campaign.description}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {!isCountingSessionActive && campaign.status === 'ACTIVE' && (
            <Button onClick={startCountingSession}>
              <Play className="w-4 h-4 mr-2" />
              Iniciar Contagem
            </Button>
          )}
          {isCountingSessionActive && (
            <Button variant="outline" onClick={endCountingSession}>
              <Pause className="w-4 h-4 mr-2" />
              Pausar
            </Button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      {countingItems.length > 0 && (
        <GlassCard className="p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-text-muted">Progresso da Contagem</span>
            <span className="text-sm font-medium text-text-primary">{countingProgress}%</span>
          </div>
          <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-blue-mid to-magenta-mid rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${countingProgress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs text-text-muted">
            <span>{countingItems.filter(i => i.counted).length} de {countingItems.length} itens</span>
            <span>{campaign.total_items_to_count} itens totais</span>
          </div>
        </GlassCard>
      )}

      {/* Counting Session */}
      {isCountingSessionActive && currentItem && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Current Item */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <Package className="w-4 h-4 text-blue-light" />
                  <GlassCardTitle>Item Atual</GlassCardTitle>
                </div>
                <Badge variant="outline">
                  {currentItemIndex + 1} de {countingItems.length}
                </Badge>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-4">
                {/* Item Info */}
                <div className="p-4 bg-white/5 rounded-lg">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-lg font-semibold text-text-primary">
                        {currentItem.partNumber}
                      </p>
                      <p className="text-sm text-text-muted flex items-center gap-1 mt-1">
                        <MapPin className="w-3 h-3" />
                        {currentItem.locationId}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-text-muted">Esperado</p>
                      <p className="text-2xl font-bold text-text-primary">
                        {currentItem.expectedQuantity}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Count Input */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Quantidade Contada *
                  </label>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCountedQuantity(Math.max(0, countedQuantity - 1))}
                    >
                      <Minus className="w-4 h-4" />
                    </Button>
                    <Input
                      type="number"
                      min="0"
                      value={countedQuantity}
                      onChange={(e) => setCountedQuantity(Number(e.target.value))}
                      className="bg-white/5 border-border text-center text-lg"
                    />
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => setCountedQuantity(countedQuantity + 1)}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Serial Scanner */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Camera className="w-4 h-4 inline mr-2" />
                    Seriais Escaneados
                  </label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      placeholder="Digite ou escaneie o serial..."
                      value={serialInput}
                      onChange={(e) => setSerialInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddSerial()}
                      className="bg-white/5 border-border"
                    />
                    <Button onClick={handleAddSerial} variant="outline">
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                  {scannedSerials.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {scannedSerials.map((serial, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs">
                          {serial}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                {/* Notes */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Observacoes
                  </label>
                  <textarea
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[60px] resize-none"
                    placeholder="Observacoes opcionais..."
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>

                {/* Navigation */}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={goToPreviousItem}
                    disabled={currentItemIndex === 0}
                    className="flex-1"
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Anterior
                  </Button>
                  <Button
                    onClick={handleSubmitCount}
                    disabled={isSubmitting}
                    className="flex-1"
                  >
                    {isSubmitting ? (
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                    )}
                    Confirmar
                  </Button>
                  <Button
                    variant="outline"
                    onClick={goToNextItem}
                    disabled={currentItemIndex === countingItems.length - 1}
                    className="flex-1"
                  >
                    Pular
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Divergences */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                <GlassCardTitle>Divergencias Detectadas</GlassCardTitle>
                <Badge variant="outline">{divergences.length}</Badge>
              </div>
            </GlassCardHeader>
            <GlassCardContent>
              {divergences.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <CheckCircle2 className="w-12 h-12 text-green-400 mb-3" />
                  <p className="text-sm text-text-muted">
                    Nenhuma divergencia encontrada ainda
                  </p>
                </div>
              ) : (
                <ScrollArea className="max-h-[400px]">
                  <div className="space-y-2">
                    {divergences.map((div) => (
                      <div
                        key={div.id}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${
                            div.type === 'POSITIVE' ? 'bg-green-400' :
                            div.type === 'NEGATIVE' ? 'bg-red-400' : 'bg-yellow-400'
                          }`} />
                          <div>
                            <p className="text-sm font-medium text-text-primary">
                              {div.part_number}
                            </p>
                            <p className="text-xs text-text-muted">
                              {div.location_name || div.location_id}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge className={DIVERGENCE_TYPE_COLORS[div.type] || 'bg-gray-500/20'}>
                            {DIVERGENCE_TYPE_LABELS[div.type] || div.type}
                          </Badge>
                          <p className="text-xs text-text-muted mt-1">
                            {div.expected_quantity} → {div.counted_quantity}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>
      )}

      {/* Campaign Info (when not counting) */}
      {!isCountingSessionActive && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Itens a Contar</p>
            <p className="text-2xl font-bold text-text-primary">{campaign.total_items_to_count}</p>
          </GlassCard>
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Itens Contados</p>
            <p className="text-2xl font-bold text-green-400">{campaign.items_counted}</p>
          </GlassCard>
          <GlassCard className="p-4">
            <p className="text-xs text-text-muted mb-1">Divergencias</p>
            <p className="text-2xl font-bold text-yellow-400">{campaign.divergences_found}</p>
          </GlassCard>
        </div>
      )}
    </div>
  );
}
