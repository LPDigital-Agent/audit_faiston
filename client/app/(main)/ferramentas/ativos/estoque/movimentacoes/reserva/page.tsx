'use client';

// =============================================================================
// Reserva Page - SGA Inventory Module
// =============================================================================
// Material reservation form for project/chamado allocation.
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
  Calendar,
  ArrowLeft,
  Package,
  MapPin,
  Briefcase,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  Clock,
  X,
} from 'lucide-react';
import { useAssetManagement, useMovementMutations, useMovementValidation } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function ReservaPage() {
  const { locations, partNumbers, projects } = useAssetManagement();
  const { createReservation } = useMovementMutations();
  const { validate, isValidating, violations, warnings } = useMovementValidation();

  const [partNumber, setPartNumber] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [projectId, setProjectId] = useState('');
  const [locationId, setLocationId] = useState('');
  const [chamadoNumber, setChamadoNumber] = useState('');
  const [notes, setNotes] = useState('');

  // Handle submit
  const handleSubmit = async () => {
    if (!partNumber || !projectId || quantity <= 0) return;

    try {
      await createReservation.mutateAsync({
        part_number: partNumber,
        quantity,
        project_id: projectId,
        location_id: locationId || undefined,
        chamado_number: chamadoNumber || undefined,
        notes: notes || undefined,
      });

      // Reset form
      setPartNumber('');
      setQuantity(1);
      setProjectId('');
      setLocationId('');
      setChamadoNumber('');
      setNotes('');
    } catch {
      // Error handled by mutation
    }
  };

  // Validate on changes
  const handleValidate = () => {
    if (partNumber && quantity > 0) {
      validate({
        operationType: 'RESERVE',
        partNumber,
        quantity,
        sourceLocationId: locationId || undefined,
        projectId: projectId || undefined,
      });
    }
  };

  const activePartNumbers = partNumbers.filter(p => p.is_active);
  const activeProjects = projects.filter(p => p.is_active);
  const warehouseLocations = locations.filter(l => l.is_active && l.type === 'WAREHOUSE');

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
            Reserva de Material
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Bloqueio temporário para projeto ou chamado
          </p>
        </div>
      </div>

      {/* Form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Form */}
        <div className="lg:col-span-2">
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-yellow-400" />
                <GlassCardTitle>Dados da Reserva</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="space-y-4">
                {/* Part Number */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Package className="w-4 h-4 inline mr-2" />
                    Part Number *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={partNumber}
                    onChange={(e) => {
                      setPartNumber(e.target.value);
                      handleValidate();
                    }}
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
                    onChange={(e) => {
                      setQuantity(Number(e.target.value));
                      handleValidate();
                    }}
                    className="bg-white/5 border-border"
                  />
                </div>

                {/* Project */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Briefcase className="w-4 h-4 inline mr-2" />
                    Projeto *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">Selecione o projeto...</option>
                    {activeProjects.map((proj) => (
                      <option key={proj.id} value={proj.id}>
                        {proj.code} - {proj.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Location (optional) */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <MapPin className="w-4 h-4 inline mr-2" />
                    Local de Origem
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={locationId}
                    onChange={(e) => setLocationId(e.target.value)}
                  >
                    <option value="">Qualquer local com saldo...</option>
                    {warehouseLocations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.code} - {loc.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Chamado Number */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Clock className="w-4 h-4 inline mr-2" />
                    Número do Chamado
                  </label>
                  <Input
                    type="text"
                    placeholder="Ex: INC0012345"
                    value={chamadoNumber}
                    onChange={(e) => setChamadoNumber(e.target.value)}
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

                {/* Validation Results */}
                {isValidating && (
                  <div className="flex items-center gap-2 text-text-muted">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Validando...</span>
                  </div>
                )}

                {violations.length > 0 && (
                  <div className="space-y-2">
                    {violations.map((v, i) => (
                      <div key={i} className="flex items-start gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                        <X className="w-4 h-4 text-red-400 mt-0.5" />
                        <p className="text-sm text-red-400">{v}</p>
                      </div>
                    ))}
                  </div>
                )}

                {warnings.length > 0 && (
                  <div className="space-y-2">
                    {warnings.map((w, i) => (
                      <div key={i} className="flex items-start gap-2 p-3 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                        <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5" />
                        <p className="text-sm text-yellow-400">{w}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Error */}
                {createReservation.error && (
                  <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-red-400" />
                    <p className="text-sm text-red-400">{createReservation.error.message}</p>
                  </div>
                )}

                {/* Submit */}
                <Button
                  className="w-full"
                  disabled={!partNumber || !projectId || quantity <= 0 || createReservation.isPending || violations.length > 0}
                  onClick={handleSubmit}
                >
                  {createReservation.isPending ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      Processando...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Criar Reserva
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
              <GlassCardTitle>Sobre Reservas</GlassCardTitle>
            </GlassCardHeader>
            <GlassCardContent>
              <div className="space-y-3 text-sm text-text-muted">
                <p>
                  <strong className="text-text-primary">O que é uma reserva?</strong>
                  <br />
                  Bloqueio temporário de material para um projeto ou chamado específico.
                </p>
                <p>
                  <strong className="text-text-primary">Expiração</strong>
                  <br />
                  Reservas expiram automaticamente após 7 dias se não forem utilizadas.
                </p>
                <p>
                  <strong className="text-text-primary">Cross-project</strong>
                  <br />
                  Reservas entre projetos diferentes requerem aprovação do gestor.
                </p>
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
                  <span className="text-text-muted">Material:</span>
                  <span className="text-text-primary">{partNumber || '-'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Quantidade:</span>
                  <span className="text-text-primary">{quantity}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Projeto:</span>
                  <span className="text-text-primary">
                    {projectId ? activeProjects.find(p => p.id === projectId)?.code || projectId : '-'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Chamado:</span>
                  <span className="text-text-primary">{chamadoNumber || '-'}</span>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
