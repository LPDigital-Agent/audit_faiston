'use client';

// =============================================================================
// Expedição Page - SGA Inventory Module (ExpeditionAgent)
// =============================================================================
// Full expedition workflow with SAP-ready data generation.
// Creates expeditions from chamados with carrier recommendations.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { useMutation, useQuery } from '@tanstack/react-query';
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
  Package,
  MapPin,
  Plus,
  Trash2,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
  Copy,
  Clipboard,
  Timer,
  DollarSign,
} from 'lucide-react';
import { useAssetManagement } from '@/hooks/ativos';
import {
  processExpeditionRequest,
  getShippingQuotes,
} from '@/services/sgaAgentcore';
import type {
  SGAExpeditionItem,
  SGAExpeditionUrgency,
  SGAExpeditionNature,
  SGASAPFormatData,
  SGAShippingQuote,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface ExpeditionFormItem extends SGAExpeditionItem {
  id: string;
}

// =============================================================================
// Constants
// =============================================================================

const URGENCY_OPTIONS: { value: SGAExpeditionUrgency; label: string; color: string }[] = [
  { value: 'LOW', label: 'Baixa', color: 'text-gray-400' },
  { value: 'NORMAL', label: 'Normal', color: 'text-blue-400' },
  { value: 'HIGH', label: 'Alta', color: 'text-yellow-400' },
  { value: 'URGENT', label: 'Urgente', color: 'text-red-400' },
];

const NATURE_OPTIONS: { value: SGAExpeditionNature; label: string }[] = [
  { value: 'USO_CONSUMO', label: 'Remessa para Uso e Consumo' },
  { value: 'CONSERTO', label: 'Remessa para Conserto' },
  { value: 'DEMONSTRACAO', label: 'Remessa para Demonstração' },
  { value: 'DEVOLUCAO', label: 'Devolução' },
  { value: 'GARANTIA', label: 'Remessa em Garantia' },
];

// =============================================================================
// Page Component
// =============================================================================

export default function ExpedicaoPage() {
  const { partNumbers, projects } = useAssetManagement();

  // Form state
  const [chamadoId, setChamadoId] = useState('');
  const [projectId, setProjectId] = useState('');
  const [destinationClient, setDestinationClient] = useState('');
  const [destinationAddress, setDestinationAddress] = useState('');
  const [destinationCep, setDestinationCep] = useState('');
  const [urgency, setUrgency] = useState<SGAExpeditionUrgency>('NORMAL');
  const [nature, setNature] = useState<SGAExpeditionNature>('USO_CONSUMO');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<ExpeditionFormItem[]>([
    { id: crypto.randomUUID(), pn_id: '', quantity: 1 },
  ]);

  // Result state
  const [sapData, setSapData] = useState<SGASAPFormatData[]>([]);
  const [quotes, setQuotes] = useState<SGAShippingQuote[]>([]);
  const [showResults, setShowResults] = useState(false);

  // Process expedition mutation
  const expeditionMutation = useMutation({
    mutationFn: async () => {
      const validItems = items.filter(item => item.pn_id && item.quantity > 0);
      if (validItems.length === 0) {
        throw new Error('Adicione pelo menos um item válido');
      }

      const result = await processExpeditionRequest({
        chamado_id: chamadoId,
        project_id: projectId,
        items: validItems.map(({ pn_id, serial, quantity }) => ({
          pn_id,
          serial,
          quantity,
        })),
        destination_client: destinationClient,
        destination_address: destinationAddress,
        urgency,
        nature,
        notes,
      });

      return result.data;
    },
    onSuccess: (data) => {
      if (data.sap_ready_data) {
        setSapData(data.sap_ready_data);
      }
      setShowResults(true);
    },
  });

  // Get quotes mutation
  const quotesMutation = useMutation({
    mutationFn: async () => {
      const result = await getShippingQuotes({
        origin_cep: '04548-005', // Faiston HQ - could be dynamic
        destination_cep: destinationCep,
        weight_kg: items.reduce((sum, item) => sum + item.quantity * 0.5, 0), // Estimate 0.5kg per unit
        dimensions: { length: 40, width: 30, height: 20 },
        value: 1000, // Default declared value
        urgency,
      });
      return result.data;
    },
    onSuccess: (data) => {
      if (data.quotes) {
        setQuotes(data.quotes);
      }
    },
  });

  // Add item
  const addItem = () => {
    setItems([...items, { id: crypto.randomUUID(), pn_id: '', quantity: 1 }]);
  };

  // Remove item
  const removeItem = (id: string) => {
    if (items.length > 1) {
      setItems(items.filter(item => item.id !== id));
    }
  };

  // Update item
  const updateItem = (id: string, field: keyof ExpeditionFormItem, value: string | number) => {
    setItems(items.map(item =>
      item.id === id ? { ...item, [field]: value } : item
    ));
  };

  // Copy SAP data to clipboard
  const copySAPData = (data: SGASAPFormatData) => {
    const text = `Cliente: ${data.cliente}
Item: ${data.item_numero}
Quantidade: ${data.quantidade}
Depósito: ${data.deposito}
Utilização: ${data.utilizacao}
Incoterms: ${data.incoterms}
Transportadora: ${data.transportadora}
Natureza: ${data.natureza_operacao}
Observação: ${data.observacao}`;

    navigator.clipboard.writeText(text);
  };

  // Handle submit
  const handleSubmit = async () => {
    if (!chamadoId || !projectId || !destinationClient) return;
    expeditionMutation.mutate();
  };

  const isLoading = expeditionMutation.isPending;

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
            <Truck className="w-5 h-5 text-blue-light" />
            Nova Expedição
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Criar expedição com dados prontos para NF SAP
          </p>
        </div>
        <Link href="/ferramentas/ativos/estoque/expedicao/cotacao">
          <Button variant="outline" size="sm">
            <DollarSign className="w-4 h-4 mr-1" />
            Cotação de Frete
          </Button>
        </Link>
      </div>

      {/* Expedition Form */}
      {!showResults && (
        <GlassCard>
          <GlassCardHeader>
            <GlassCardTitle>Dados da Expedição</GlassCardTitle>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-6">
              {/* Basic Info Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Chamado ID */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Número do Chamado *
                  </label>
                  <Input
                    placeholder="Ex: CHAMADO-12345"
                    value={chamadoId}
                    onChange={(e) => setChamadoId(e.target.value)}
                    className="bg-white/5 border-border"
                  />
                </div>

                {/* Project */}
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Projeto *
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">Selecione o projeto...</option>
                    {projects?.filter(p => p.is_active).map((proj) => (
                      <option key={proj.id} value={proj.id}>
                        {proj.code} - {proj.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Client & Address */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <MapPin className="w-4 h-4 inline mr-1" />
                    Cliente Destino *
                  </label>
                  <Input
                    placeholder="Nome do cliente ou CNPJ"
                    value={destinationClient}
                    onChange={(e) => setDestinationClient(e.target.value)}
                    className="bg-white/5 border-border"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    CEP Destino
                  </label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="00000-000"
                      value={destinationCep}
                      onChange={(e) => setDestinationCep(e.target.value)}
                      className="bg-white/5 border-border flex-1"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => quotesMutation.mutate()}
                      disabled={!destinationCep || quotesMutation.isPending}
                    >
                      {quotesMutation.isPending ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        'Cotar'
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Endereço Completo
                </label>
                <Input
                  placeholder="Rua, número, complemento, cidade, estado"
                  value={destinationAddress}
                  onChange={(e) => setDestinationAddress(e.target.value)}
                  className="bg-white/5 border-border"
                />
              </div>

              {/* Carrier Quotes */}
              {quotes.length > 0 && (
                <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                  <p className="text-sm font-medium text-blue-400 mb-3">Cotações Disponíveis:</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
                    {quotes.filter(q => q.available).map((quote, idx) => (
                      <div key={idx} className="p-2 bg-white/5 rounded-md text-xs">
                        <p className="font-medium text-text-primary">{quote.carrier}</p>
                        <p className="text-text-muted">{quote.modal}</p>
                        <p className="text-green-400">R$ {quote.price.toFixed(2)}</p>
                        <p className="text-text-muted">{quote.delivery_days} dias</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Urgency & Nature */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Timer className="w-4 h-4 inline mr-1" />
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

                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Natureza da Operação
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={nature}
                    onChange={(e) => setNature(e.target.value as SGAExpeditionNature)}
                  >
                    {NATURE_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Items */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <label className="text-sm font-medium text-text-primary">
                    <Package className="w-4 h-4 inline mr-1" />
                    Itens ({items.length})
                  </label>
                  <Button variant="ghost" size="sm" onClick={addItem}>
                    <Plus className="w-4 h-4 mr-1" />
                    Adicionar
                  </Button>
                </div>

                <div className="space-y-3">
                  {items.map((item, index) => (
                    <div key={item.id} className="flex gap-2 items-start">
                      <div className="flex-1">
                        <select
                          className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                          value={item.pn_id}
                          onChange={(e) => updateItem(item.id, 'pn_id', e.target.value)}
                        >
                          <option value="">Selecione o Part Number...</option>
                          {partNumbers?.filter(p => p.is_active).map((pn) => (
                            <option key={pn.id} value={pn.id}>
                              {pn.part_number} - {pn.description}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Input
                        type="text"
                        placeholder="Serial (opcional)"
                        value={item.serial || ''}
                        onChange={(e) => updateItem(item.id, 'serial', e.target.value)}
                        className="w-32 bg-white/5 border-border"
                      />
                      <Input
                        type="number"
                        min={1}
                        value={item.quantity}
                        onChange={(e) => updateItem(item.id, 'quantity', parseInt(e.target.value) || 1)}
                        className="w-20 bg-white/5 border-border"
                      />
                      {items.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeItem(item.id)}
                          className="text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Observações
                </label>
                <textarea
                  className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[80px] resize-none"
                  placeholder="Observações adicionais..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              {/* Error */}
              {expeditionMutation.error && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <p className="text-sm text-red-400">{expeditionMutation.error.message}</p>
                </div>
              )}

              {/* Submit */}
              <Button
                className="w-full"
                disabled={!chamadoId || !projectId || !destinationClient || isLoading}
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
                    Criar Expedição
                  </>
                )}
              </Button>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Results: SAP-Ready Data */}
      {showResults && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between">
              <GlassCardTitle className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
                Expedição Criada - Dados para SAP
              </GlassCardTitle>
              <Button variant="ghost" size="sm" onClick={() => setShowResults(false)}>
                Nova Expedição
              </Button>
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            <p className="text-sm text-text-muted mb-4">
              Copie os dados abaixo para colar no SAP e emitir a NF:
            </p>

            <div className="space-y-4">
              {sapData.map((data, index) => (
                <div key={index} className="p-4 bg-white/5 border border-border rounded-lg relative">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2"
                    onClick={() => copySAPData(data)}
                  >
                    <Copy className="w-4 h-4 mr-1" />
                    Copiar
                  </Button>

                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-text-muted">Cliente</p>
                      <p className="text-text-primary font-mono">{data.cliente}</p>
                    </div>
                    <div>
                      <p className="text-text-muted">Item</p>
                      <p className="text-text-primary font-mono">{data.item_numero}</p>
                    </div>
                    <div>
                      <p className="text-text-muted">Quantidade</p>
                      <p className="text-text-primary font-mono">{data.quantidade}</p>
                    </div>
                    <div>
                      <p className="text-text-muted">Depósito</p>
                      <p className="text-text-primary font-mono">{data.deposito}</p>
                    </div>
                    <div>
                      <p className="text-text-muted">Utilização</p>
                      <p className="text-text-primary font-mono">{data.utilizacao}</p>
                    </div>
                    <div>
                      <p className="text-text-muted">Transportadora</p>
                      <p className="text-text-primary font-mono">{data.transportadora || '-'}</p>
                    </div>
                    <div className="col-span-2 md:col-span-3">
                      <p className="text-text-muted">Natureza</p>
                      <p className="text-text-primary font-mono">{data.natureza_operacao}</p>
                    </div>
                    <div className="col-span-2 md:col-span-3">
                      <p className="text-text-muted">Observação</p>
                      <p className="text-text-primary font-mono">{data.observacao}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </GlassCardContent>
        </GlassCard>
      )}
    </div>
  );
}
