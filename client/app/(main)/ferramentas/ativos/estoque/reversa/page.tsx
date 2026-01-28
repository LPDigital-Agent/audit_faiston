'use client';

// =============================================================================
// Reversa Page - SGA Inventory Module (ReverseAgent)
// =============================================================================
// Equipment returns and reverse logistics with automatic depot routing.
// Handles returns from customers, field techs, and branches.
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
import { Input } from '@/components/ui/input';
import {
  RotateCcw,
  ArrowLeft,
  Search,
  Package,
  MapPin,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  Warehouse,
  User,
  FileText,
  Camera,
} from 'lucide-react';
import {
  processReturnNew,
  validateReturnOrigin,
  evaluateReturnCondition,
} from '@/services/sgaAgentcore';
import type {
  SGAReverseOriginType,
  SGAEquipmentOwner,
  SGAEquipmentCondition,
  SGAReturnReason,
  SGAAsset,
} from '@/lib/ativos/types';

// =============================================================================
// Constants
// =============================================================================

const ORIGIN_OPTIONS: { value: SGAReverseOriginType; label: string }[] = [
  { value: 'CUSTOMER', label: 'Cliente' },
  { value: 'FIELD_TECH', label: 'Técnico de Campo' },
  { value: 'BRANCH', label: 'Filial' },
  { value: 'THIRD_PARTY', label: 'Terceiro' },
];

const OWNER_OPTIONS: { value: SGAEquipmentOwner; label: string; color: string }[] = [
  { value: 'FAISTON', label: 'Faiston', color: 'text-blue-400' },
  { value: 'NTT', label: 'NTT', color: 'text-purple-400' },
  { value: 'TERCEIROS', label: 'Terceiros', color: 'text-gray-400' },
];

const CONDITION_OPTIONS: { value: SGAEquipmentCondition; label: string; color: string }[] = [
  { value: 'FUNCIONAL', label: 'Funcional', color: 'text-green-400' },
  { value: 'DEFEITUOSO', label: 'Defeituoso', color: 'text-yellow-400' },
  { value: 'INSERVIVEL', label: 'Inservível', color: 'text-red-400' },
];

const REASON_OPTIONS: { value: SGAReturnReason; label: string }[] = [
  { value: 'CONSERTO_CONCLUIDO', label: 'Conserto Concluído' },
  { value: 'DEVOLUCAO_CLIENTE', label: 'Devolução do Cliente' },
  { value: 'FIM_CONTRATO', label: 'Fim de Contrato' },
  { value: 'UPGRADE', label: 'Upgrade de Equipamento' },
  { value: 'TROCA_GARANTIA', label: 'Troca em Garantia' },
  { value: 'EQUIPAMENTO_DEFEITUOSO', label: 'Equipamento Defeituoso' },
  { value: 'OUTRO', label: 'Outro' },
];

const DEPOT_NAMES: Record<string, string> = {
  '01': 'Recebimento',
  '03': 'BAD (Defeituosos Faiston)',
  '03.01': 'BAD NTT (Defeituosos NTT)',
  '04': 'Descarte',
  '05': 'Itens de Terceiros',
  '06': 'Depósito de Terceiros',
};

// =============================================================================
// Page Component
// =============================================================================

export default function ReversaPage() {
  // Form state
  const [serial, setSerial] = useState('');
  const [originType, setOriginType] = useState<SGAReverseOriginType>('CUSTOMER');
  const [originAddress, setOriginAddress] = useState('');
  const [owner, setOwner] = useState<SGAEquipmentOwner>('FAISTON');
  const [condition, setCondition] = useState<SGAEquipmentCondition>('FUNCIONAL');
  const [returnReason, setReturnReason] = useState<SGAReturnReason>('DEVOLUCAO_CLIENTE');
  const [chamadoId, setChamadoId] = useState('');
  const [projectId, setProjectId] = useState('');
  const [notes, setNotes] = useState('');
  const [conditionDescription, setConditionDescription] = useState('');

  // Result state
  const [validatedAsset, setValidatedAsset] = useState<SGAAsset | null>(null);
  const [suggestedDepot, setSuggestedDepot] = useState<string | null>(null);
  const [returnResult, setReturnResult] = useState<{
    success: boolean;
    depot: string;
    depotName: string;
    message: string;
    requiresAnalysis: boolean;
  } | null>(null);

  // Validate serial mutation
  const validateMutation = useMutation({
    mutationFn: async () => {
      const result = await validateReturnOrigin({
        serial,
        claimed_origin: originAddress,
      });
      return result.data;
    },
    onSuccess: (data) => {
      if (data.found && data.asset) {
        setValidatedAsset(data.asset);
      }
    },
  });

  // Evaluate condition mutation
  const evaluateMutation = useMutation({
    mutationFn: async () => {
      const result = await evaluateReturnCondition({
        serial,
        owner,
        condition_description: conditionDescription,
      });
      return result.data;
    },
    onSuccess: (data) => {
      if (data.detected_condition) {
        setCondition(data.detected_condition);
      }
      if (data.recommended_depot) {
        setSuggestedDepot(data.recommended_depot);
      }
    },
  });

  // Process return mutation
  const returnMutation = useMutation({
    mutationFn: async () => {
      const result = await processReturnNew({
        serial,
        origin_type: originType,
        origin_address: originAddress,
        owner,
        condition,
        return_reason: returnReason,
        chamado_id: chamadoId || undefined,
        project_id: projectId || undefined,
        notes,
      });
      return result.data;
    },
    onSuccess: (data) => {
      setReturnResult({
        success: data.success,
        depot: data.destination_depot,
        depotName: data.destination_depot_name || DEPOT_NAMES[data.destination_depot] || data.destination_depot,
        message: data.message,
        requiresAnalysis: data.requires_analysis,
      });
    },
  });

  // Handle validate serial
  const handleValidate = () => {
    if (!serial) return;
    validateMutation.mutate();
  };

  // Handle evaluate condition
  const handleEvaluate = () => {
    if (!conditionDescription) return;
    evaluateMutation.mutate();
  };

  // Handle submit return
  const handleSubmit = () => {
    if (!serial || !originType) return;
    returnMutation.mutate();
  };

  // Reset form
  const handleReset = () => {
    setSerial('');
    setOriginAddress('');
    setConditionDescription('');
    setChamadoId('');
    setProjectId('');
    setNotes('');
    setValidatedAsset(null);
    setSuggestedDepot(null);
    setReturnResult(null);
    setOwner('FAISTON');
    setCondition('FUNCIONAL');
    setReturnReason('DEVOLUCAO_CLIENTE');
    setOriginType('CUSTOMER');
  };

  const isLoading = returnMutation.isPending;

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
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-purple-400" />
            Reversa / Devolução
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Processar retorno de equipamentos com roteamento automático para depósito
          </p>
        </div>
      </div>

      {/* Success Result */}
      {returnResult && returnResult.success && (
        <GlassCard>
          <GlassCardContent className="py-8">
            <div className="text-center">
              <CheckCircle2 className="w-12 h-12 text-green-400 mx-auto mb-4" />
              <h2 className="text-lg font-semibold text-text-primary mb-2">
                Reversa Processada!
              </h2>
              <p className="text-text-muted mb-4">{returnResult.message}</p>

              <div className="p-4 bg-white/5 border border-border rounded-lg inline-block">
                <p className="text-sm text-text-muted">Depósito de Destino:</p>
                <p className="text-xl font-bold text-text-primary">
                  {returnResult.depot} - {returnResult.depotName}
                </p>
              </div>

              {returnResult.requiresAnalysis && (
                <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <AlertTriangle className="w-4 h-4 text-yellow-400 inline mr-2" />
                  <span className="text-sm text-yellow-400">
                    Equipamento requer análise técnica antes de disponibilização
                  </span>
                </div>
              )}

              <Button className="mt-6" onClick={handleReset}>
                Nova Reversa
              </Button>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Form */}
      {(!returnResult || !returnResult.success) && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Form */}
          <div className="lg:col-span-2">
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle>Dados da Reversa</GlassCardTitle>
              </GlassCardHeader>

              <GlassCardContent>
                <div className="space-y-6">
                  {/* Serial Number */}
                  <div>
                    <label className="text-sm font-medium text-text-primary mb-2 block">
                      <Package className="w-4 h-4 inline mr-1" />
                      Número de Série *
                    </label>
                    <div className="flex gap-2">
                      <Input
                        placeholder="Digite ou escaneie o serial..."
                        value={serial}
                        onChange={(e) => setSerial(e.target.value)}
                        className="bg-white/5 border-border flex-1"
                      />
                      <Button
                        variant="outline"
                        onClick={handleValidate}
                        disabled={!serial || validateMutation.isPending}
                      >
                        {validateMutation.isPending ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <Search className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                    {validatedAsset && (
                      <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded-md">
                        <p className="text-sm text-green-400">
                          ✓ {validatedAsset.part_number} - {validatedAsset.description}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Origin */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        <User className="w-4 h-4 inline mr-1" />
                        Tipo de Origem
                      </label>
                      <select
                        className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                        value={originType}
                        onChange={(e) => setOriginType(e.target.value as SGAReverseOriginType)}
                      >
                        {ORIGIN_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        <MapPin className="w-4 h-4 inline mr-1" />
                        Endereço de Origem
                      </label>
                      <Input
                        placeholder="Cidade, estado ou endereço..."
                        value={originAddress}
                        onChange={(e) => setOriginAddress(e.target.value)}
                        className="bg-white/5 border-border"
                      />
                    </div>
                  </div>

                  {/* Owner & Condition */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        <Warehouse className="w-4 h-4 inline mr-1" />
                        Proprietário do Equipamento
                      </label>
                      <select
                        className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                        value={owner}
                        onChange={(e) => setOwner(e.target.value as SGAEquipmentOwner)}
                      >
                        {OWNER_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        Condição
                      </label>
                      <div className="flex gap-2">
                        {CONDITION_OPTIONS.map(opt => (
                          <button
                            key={opt.value}
                            type="button"
                            className={`flex-1 px-3 py-2 rounded-md text-sm border transition-all ${
                              condition === opt.value
                                ? `bg-white/10 border-white/30 ${opt.color}`
                                : 'bg-white/5 border-border text-text-muted hover:bg-white/10'
                            }`}
                            onClick={() => setCondition(opt.value)}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Reason */}
                  <div>
                    <label className="text-sm font-medium text-text-primary mb-2 block">
                      <FileText className="w-4 h-4 inline mr-1" />
                      Motivo da Devolução
                    </label>
                    <select
                      className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                      value={returnReason}
                      onChange={(e) => setReturnReason(e.target.value as SGAReturnReason)}
                    >
                      {REASON_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Chamado & Project (optional) */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        Chamado (opcional)
                      </label>
                      <Input
                        placeholder="CHAMADO-12345"
                        value={chamadoId}
                        onChange={(e) => setChamadoId(e.target.value)}
                        className="bg-white/5 border-border"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-text-primary mb-2 block">
                        Projeto (opcional)
                      </label>
                      <Input
                        placeholder="ID do projeto"
                        value={projectId}
                        onChange={(e) => setProjectId(e.target.value)}
                        className="bg-white/5 border-border"
                      />
                    </div>
                  </div>

                  {/* Notes */}
                  <div>
                    <label className="text-sm font-medium text-text-primary mb-2 block">
                      Observações
                    </label>
                    <textarea
                      className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[80px] resize-none"
                      placeholder="Observações sobre a devolução..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>

                  {/* Error */}
                  {returnMutation.error && (
                    <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                      <AlertTriangle className="w-5 h-5 text-red-400" />
                      <p className="text-sm text-red-400">{returnMutation.error.message}</p>
                    </div>
                  )}

                  {/* Submit */}
                  <Button
                    className="w-full"
                    disabled={!serial || isLoading}
                    onClick={handleSubmit}
                  >
                    {isLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Processando...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                        Processar Reversa
                      </>
                    )}
                  </Button>
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>

          {/* Sidebar: AI Condition Evaluation */}
          <div>
            <GlassCard>
              <GlassCardHeader>
                <GlassCardTitle className="flex items-center gap-2">
                  <Camera className="w-4 h-4" />
                  Avaliação AI
                </GlassCardTitle>
              </GlassCardHeader>

              <GlassCardContent>
                <div className="space-y-4">
                  <p className="text-sm text-text-muted">
                    Descreva o estado do equipamento para sugestão automática de depósito.
                  </p>

                  <div>
                    <label className="text-sm font-medium text-text-primary mb-2 block">
                      Descrição da Condição
                    </label>
                    <textarea
                      className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[100px] resize-none"
                      placeholder="Ex: Equipamento com tela rachada, liga mas não exibe imagem..."
                      value={conditionDescription}
                      onChange={(e) => setConditionDescription(e.target.value)}
                    />
                  </div>

                  <Button
                    variant="outline"
                    className="w-full"
                    disabled={!conditionDescription || !serial || evaluateMutation.isPending}
                    onClick={handleEvaluate}
                  >
                    {evaluateMutation.isPending ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Analisando...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4 mr-2" />
                        Avaliar com IA
                      </>
                    )}
                  </Button>

                  {/* Suggested Depot */}
                  {suggestedDepot && (
                    <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                      <p className="text-sm text-purple-400 font-medium mb-2">
                        Sugestão NEXO AI:
                      </p>
                      <p className="text-lg font-bold text-text-primary">
                        {suggestedDepot} - {DEPOT_NAMES[suggestedDepot] || suggestedDepot}
                      </p>
                    </div>
                  )}

                  {/* Depot Legend */}
                  <div className="pt-4 border-t border-border">
                    <p className="text-xs text-text-muted mb-2">Depósitos SAP:</p>
                    <div className="space-y-1 text-xs">
                      {Object.entries(DEPOT_NAMES).map(([code, name]) => (
                        <div key={code} className="flex justify-between text-text-muted">
                          <span>{code}</span>
                          <span>{name}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </GlassCardContent>
            </GlassCard>
          </div>
        </div>
      )}
    </div>
  );
}
