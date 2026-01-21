'use client';

// =============================================================================
// Ajuste Page - SGA Inventory Module
// =============================================================================
// Stock adjustment form - ALWAYS requires HIL approval.
// Used for inventory reconciliation and corrections.
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
  AlertTriangle,
  ArrowLeft,
  Package,
  MapPin,
  Plus,
  Minus,
  CheckCircle2,
  RefreshCw,
  Shield,
  FileText,
  Clock,
} from 'lucide-react';
import { useAssetManagement, useInventoryCount } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function AjustePage() {
  const { locations, partNumbers } = useAssetManagement();
  const { submitAdjustmentProposal, activeCampaign } = useInventoryCount();

  const [adjustmentType, setAdjustmentType] = useState<'IN' | 'OUT'>('IN');
  const [partNumber, setPartNumber] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [locationId, setLocationId] = useState('');
  const [reason, setReason] = useState('');
  const [evidenceNotes, setEvidenceNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Handle submit
  const handleSubmit = async () => {
    if (!partNumber || !locationId || !reason || quantity <= 0) {
      setError('Preencha todos os campos obrigatórios');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(false);

    try {
      await submitAdjustmentProposal(partNumber, locationId, reason);
      setSuccess(true);

      // Reset form
      setPartNumber('');
      setQuantity(1);
      setLocationId('');
      setReason('');
      setEvidenceNotes('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar proposta de ajuste');
    } finally {
      setIsSubmitting(false);
    }
  };

  const activePartNumbers = partNumbers.filter(p => p.is_active);
  const warehouseLocations = locations.filter(l => l.is_active && l.type === 'WAREHOUSE');

  const reasonOptions = [
    { value: 'DIVERGENCIA_INVENTARIO', label: 'Divergência de Inventário' },
    { value: 'CORRECAO_SISTEMA', label: 'Correção de Sistema' },
    { value: 'DANIFICADO', label: 'Material Danificado' },
    { value: 'EXTRAVIO', label: 'Extravio' },
    { value: 'LOCALIZACAO_INCORRETA', label: 'Localização Incorreta' },
    { value: 'OUTRO', label: 'Outro' },
  ];

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
            Ajuste de Estoque
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Correção de saldos (requer aprovação)
          </p>
        </div>
        <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
          <Shield className="w-3 h-3 mr-1" />
          Requer Aprovação
        </Badge>
      </div>

      {/* HIL Warning Banner */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <GlassCard className="border-yellow-500/30 bg-yellow-500/5">
          <GlassCardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-yellow-400">
                  Ajustes Sempre Requerem Aprovação
                </p>
                <p className="text-xs text-yellow-400/80 mt-1">
                  Ajustes de estoque afetam saldos e rastreabilidade. Todas as solicitações
                  serão enviadas para o gestor responsável antes de serem efetivadas.
                </p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      </motion.div>

      {/* Form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Form */}
        <div className="lg:col-span-2">
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-400" />
                <GlassCardTitle>Proposta de Ajuste</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="space-y-4">
                {/* Adjustment Type */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Tipo de Ajuste *
                  </label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={adjustmentType === 'IN' ? 'default' : 'outline'}
                      className={`flex-1 ${adjustmentType === 'IN' ? 'bg-green-500/20 hover:bg-green-500/30 text-green-400 border-green-500/30' : ''}`}
                      onClick={() => setAdjustmentType('IN')}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Entrada (+)
                    </Button>
                    <Button
                      type="button"
                      variant={adjustmentType === 'OUT' ? 'default' : 'outline'}
                      className={`flex-1 ${adjustmentType === 'OUT' ? 'bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30' : ''}`}
                      onClick={() => setAdjustmentType('OUT')}
                    >
                      <Minus className="w-4 h-4 mr-2" />
                      Saída (-)
                    </Button>
                  </div>
                </div>

                {/* Part Number */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Package className="w-4 h-4 inline mr-2" />
                    Part Number *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={partNumber}
                    onChange={(e) => setPartNumber(e.target.value)}
                  >
                    <option value="">Selecione o material...</option>
                    {activePartNumbers.map((pn) => (
                      <option key={pn.id} value={pn.part_number}>
                        {pn.part_number} - {pn.description}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Quantity */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Quantidade *
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                    className="bg-white/5 border-border"
                  />
                </div>

                {/* Location */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <MapPin className="w-4 h-4 inline mr-2" />
                    Local *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={locationId}
                    onChange={(e) => setLocationId(e.target.value)}
                  >
                    <option value="">Selecione o local...</option>
                    {warehouseLocations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.code} - {loc.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Reason */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <FileText className="w-4 h-4 inline mr-2" />
                    Motivo *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  >
                    <option value="">Selecione o motivo...</option>
                    {reasonOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Evidence/Notes */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Justificativa Detalhada *
                  </label>
                  <textarea
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[120px] resize-none"
                    placeholder="Descreva detalhadamente o motivo do ajuste. Inclua referências a contagens, fotos, ou outros documentos de suporte..."
                    value={evidenceNotes}
                    onChange={(e) => setEvidenceNotes(e.target.value)}
                  />
                </div>

                {/* Campaign Reference */}
                {activeCampaign && (
                  <div className="flex items-center gap-2 p-3 bg-blue-500/20 border border-blue-500/30 rounded-lg">
                    <Clock className="w-4 h-4 text-blue-400" />
                    <p className="text-sm text-blue-400">
                      Vinculado à campanha: <strong>{activeCampaign.name}</strong>
                    </p>
                  </div>
                )}

                {/* Success */}
                {success && (
                  <div className="flex items-center gap-2 p-3 bg-green-500/20 border border-green-500/30 rounded-lg">
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    <p className="text-sm text-green-400">
                      Proposta de ajuste enviada para aprovação!
                    </p>
                  </div>
                )}

                {/* Error */}
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {/* Submit */}
                <Button
                  className="w-full"
                  disabled={!partNumber || !locationId || !reason || quantity <= 0 || !evidenceNotes || isSubmitting}
                  onClick={handleSubmit}
                >
                  {isSubmitting ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Enviando...
                    </>
                  ) : (
                    <>
                      <Shield className="w-4 h-4 mr-2" />
                      Enviar para Aprovação
                    </>
                  )}
                </Button>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Info Panel */}
        <div className="space-y-6">
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle>Fluxo de Aprovação</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-xs text-blue-400 font-bold">
                    1
                  </div>
                  <div>
                    <p className="text-sm text-text-primary">Proposta Criada</p>
                    <p className="text-xs text-text-muted">Você está aqui</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-yellow-500/20 flex items-center justify-center text-xs text-yellow-400 font-bold">
                    2
                  </div>
                  <div>
                    <p className="text-sm text-text-primary">Revisão do Gestor</p>
                    <p className="text-xs text-text-muted">Análise e validação</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center text-xs text-green-400 font-bold">
                    3
                  </div>
                  <div>
                    <p className="text-sm text-text-primary">Ajuste Aplicado</p>
                    <p className="text-xs text-text-muted">Saldo atualizado</p>
                  </div>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Summary */}
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle>Resumo</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Tipo:</span>
                  <Badge className={adjustmentType === 'IN' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}>
                    {adjustmentType === 'IN' ? 'Entrada (+)' : 'Saída (-)'}
                  </Badge>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Material:</span>
                  <span className="text-text-primary">{partNumber || '-'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Quantidade:</span>
                  <span className={adjustmentType === 'IN' ? 'text-green-400' : 'text-red-400'}>
                    {adjustmentType === 'IN' ? '+' : '-'}{quantity}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Local:</span>
                  <span className="text-text-primary">
                    {locationId ? warehouseLocations.find(l => l.id === locationId)?.code || locationId : '-'}
                  </span>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
