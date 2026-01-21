'use client';

// =============================================================================
// Saida/Expedição Page - SGA Inventory Module
// =============================================================================
// Material expedition (shipping to field).
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
import {
  Truck,
  ArrowLeft,
  Search,
  Package,
  MapPin,
  Calendar,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { useAssetManagement, useMovementMutations, useMovementValidation } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function SaidaPage() {
  const { locations, partNumbers } = useAssetManagement();
  const { processExpedition } = useMovementMutations();
  const { validate, isValidating, isValid, violations, warnings } = useMovementValidation();

  const [selectedReservation, setSelectedReservation] = useState('');
  const [partNumber, setPartNumber] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [destinationLocation, setDestinationLocation] = useState('');
  const [recipient, setRecipient] = useState('');
  const [notes, setNotes] = useState('');

  // Handle submit
  const handleSubmit = async () => {
    if (!partNumber || !destinationLocation) return;

    try {
      await processExpedition.mutateAsync({
        reservation_id: selectedReservation || '',
        part_number: partNumber,
        quantity,
        destination_location_id: destinationLocation,
        notes,
      });

      // Reset form
      setSelectedReservation('');
      setPartNumber('');
      setQuantity(1);
      setDestinationLocation('');
      setRecipient('');
      setNotes('');
    } catch {
      // Error handled by hook
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/movimentacoes">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Movimentações
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Expedição
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Envio de materiais para campo
          </p>
        </div>
      </div>

      {/* Expedition Form */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <Truck className="w-4 h-4 text-blue-light" />
            <GlassCardTitle>Nova Expedição</GlassCardTitle>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          <div className="space-y-6">
            {/* Part Number Selection */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                <Package className="w-4 h-4 inline mr-2" />
                Part Number
              </label>
              <select
                className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                value={partNumber}
                onChange={(e) => setPartNumber(e.target.value)}
              >
                <option value="">Selecione o Part Number...</option>
                {partNumbers.filter(p => p.is_active).map((pn) => (
                  <option key={pn.id} value={pn.part_number}>
                    {pn.part_number} - {pn.description}
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                Quantidade
              </label>
              <Input
                type="number"
                min={1}
                value={quantity}
                onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                className="bg-white/5 border-border"
              />
            </div>

            {/* Destination Location */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                <MapPin className="w-4 h-4 inline mr-2" />
                Destino
              </label>
              <select
                className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                value={destinationLocation}
                onChange={(e) => setDestinationLocation(e.target.value)}
              >
                <option value="">Selecione o destino...</option>
                {locations.filter(l => l.is_active && (l.type === 'CUSTOMER' || l.type === 'TRANSIT')).map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.code} - {loc.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Recipient */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                Responsável pelo Recebimento
              </label>
              <Input
                type="text"
                placeholder="Nome do técnico ou responsável..."
                value={recipient}
                onChange={(e) => setRecipient(e.target.value)}
                className="bg-white/5 border-border"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                Observações
              </label>
              <textarea
                className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[100px] resize-none"
                placeholder="Observações adicionais..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            {/* Validation Warnings */}
            {warnings.length > 0 && (
              <div className="space-y-2">
                {warnings.map((warning, index) => (
                  <div key={index} className="flex items-center gap-2 p-3 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    <p className="text-sm text-yellow-400">{warning}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Validation Errors */}
            {violations.length > 0 && (
              <div className="space-y-2">
                {violations.map((violation, index) => (
                  <div key={index} className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    <p className="text-sm text-red-400">{violation}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {processExpedition.error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <p className="text-sm text-red-400">{processExpedition.error.message}</p>
              </div>
            )}

            {/* Submit Button */}
            <Button
              className="w-full"
              disabled={!partNumber || !destinationLocation || processExpedition.isPending}
              onClick={handleSubmit}
            >
              {processExpedition.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Processando...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Confirmar Expedição
                </>
              )}
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
