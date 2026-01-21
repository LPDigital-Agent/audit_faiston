'use client';

// =============================================================================
// Transferencia Page - SGA Inventory Module
// =============================================================================
// Asset transfer between locations.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  ArrowRightLeft,
  ArrowLeft,
  Package,
  MapPin,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';
import { useAssetManagement, useMovementMutations, useMovementValidation } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function TransferenciaPage() {
  const { locations, partNumbers } = useAssetManagement();
  const { createTransfer } = useMovementMutations();
  const { violations, warnings } = useMovementValidation();

  const [partNumber, setPartNumber] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [sourceLocation, setSourceLocation] = useState('');
  const [destinationLocation, setDestinationLocation] = useState('');
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');

  // Handle submit
  const handleSubmit = async () => {
    if (!partNumber || !sourceLocation || !destinationLocation || !reason) return;

    try {
      await createTransfer.mutateAsync({
        part_number: partNumber,
        quantity,
        source_location_id: sourceLocation,
        destination_location_id: destinationLocation,
        reason,
        notes,
      });

      // Reset form
      setPartNumber('');
      setQuantity(1);
      setSourceLocation('');
      setDestinationLocation('');
      setReason('');
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
            Transferência
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Movimentação entre locais
          </p>
        </div>
      </div>

      {/* Transfer Form */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-magenta-mid" />
            <GlassCardTitle>Nova Transferência</GlassCardTitle>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          <div className="space-y-6">
            {/* Part Number */}
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

            {/* Locations */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  <MapPin className="w-4 h-4 inline mr-2" />
                  Origem
                </label>
                <select
                  className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                  value={sourceLocation}
                  onChange={(e) => setSourceLocation(e.target.value)}
                >
                  <option value="">Selecione...</option>
                  {locations.filter(l => l.is_active).map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.code} - {loc.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-center py-2">
                <ArrowRight className="w-6 h-6 text-text-muted" />
              </div>

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
                  <option value="">Selecione...</option>
                  {locations.filter(l => l.is_active && l.id !== sourceLocation).map((loc) => (
                    <option key={loc.id} value={loc.id}>
                      {loc.code} - {loc.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Reason */}
            <div>
              <label className="text-sm font-medium text-text-primary mb-2 block">
                Motivo da Transferência
              </label>
              <select
                className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                <option value="">Selecione o motivo...</option>
                <option value="REBALANCEAMENTO">Rebalanceamento de estoque</option>
                <option value="DEMANDA_PROJETO">Demanda de projeto</option>
                <option value="MANUTENCAO">Envio para manutenção</option>
                <option value="DEVOLUCAO">Devolução</option>
                <option value="OUTROS">Outros</option>
              </select>
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

            {/* Warnings */}
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

            {/* Error */}
            {createTransfer.error && (
              <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                <p className="text-sm text-red-400">{createTransfer.error.message}</p>
              </div>
            )}

            {/* Submit */}
            <Button
              className="w-full"
              disabled={!partNumber || !sourceLocation || !destinationLocation || !reason || createTransfer.isPending}
              onClick={handleSubmit}
            >
              {createTransfer.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Processando...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Confirmar Transferência
                </>
              )}
            </Button>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
