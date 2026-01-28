'use client';

// =============================================================================
// Carrier Management Admin Page - Multi-Carrier Quote System
// =============================================================================
// Admin interface for managing CSV-based carriers.
// Allows uploading pricing tables with LLM-assisted schema detection.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Truck,
  ArrowLeft,
  Plus,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Calendar,
  User,
  MapPin,
  FileSpreadsheet,
  Settings,
  Upload,
  Trash2,
} from 'lucide-react';
import { listCarriers, deleteCarrier } from '@/services/carrierAgentcore';

// =============================================================================
// Types
// =============================================================================

interface CarrierInfo {
  carrier_id: string;
  carrier_name: string;
  display_name?: string;
  is_active: boolean;
  current_version: number;
  total_routes?: number;
  last_upload_at?: string;
  last_upload_by?: string;
}

// =============================================================================
// Page Component
// =============================================================================

export default function TransportadorasAdminPage() {
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const deleteMutation = useMutation({
    mutationFn: async (carrierId: string) => {
      const result = await deleteCarrier(carrierId);
      if (!result.data?.success) {
        throw new Error(result.data?.error || 'Falha ao excluir transportadora');
      }
      return result.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['carriers-list'] });
      setDeletingId(null);
    },
    onError: () => {
      setDeletingId(null);
    },
  });

  const handleDelete = (carrierId: string, carrierName: string) => {
    if (window.confirm(`Excluir transportadora "${carrierName}" e todos os seus dados? Esta acao nao pode ser desfeita.`)) {
      setDeletingId(carrierId);
      deleteMutation.mutate(carrierId);
    }
  };

  // Fetch carriers list
  const carriersQuery = useQuery({
    queryKey: ['carriers-list'],
    queryFn: async () => {
      const result = await listCarriers();
      return result.data?.carriers || [];
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const carriers = carriersQuery.data as CarrierInfo[] || [];

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/expedicao/cotacao">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Cotacao
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Truck className="w-5 h-5 text-blue-400" />
            Gestao de Transportadoras
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Gerencie tabelas de precos e configuracoes de transportadoras
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => carriersQuery.refetch()}
            disabled={carriersQuery.isFetching}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${carriersQuery.isFetching ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
          <Button size="sm" asChild>
            <Link href="/ferramentas/ativos/transportadoras/upload">
              <Plus className="w-4 h-4 mr-2" />
              Nova Transportadora
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <GlassCard>
          <GlassCardContent className="py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <Truck className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {carriers.length}
                </p>
                <p className="text-sm text-text-muted">Transportadoras</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        <GlassCard>
          <GlassCardContent className="py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {carriers.filter(c => c.is_active).length}
                </p>
                <p className="text-sm text-text-muted">Ativas</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>

        <GlassCard>
          <GlassCardContent className="py-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                <MapPin className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-text-primary">
                  {carriers.reduce((sum, c) => sum + (c.total_routes || 0), 0)}
                </p>
                <p className="text-sm text-text-muted">Rotas</p>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      </div>

      {/* Carriers List */}
      <GlassCard>
        <GlassCardHeader>
          <GlassCardTitle>Transportadoras Cadastradas</GlassCardTitle>
        </GlassCardHeader>

        <GlassCardContent>
          {carriersQuery.isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-6 h-6 animate-spin text-blue-400 mr-2" />
              <span className="text-text-muted">Carregando...</span>
            </div>
          ) : carriers.length === 0 ? (
            <div className="text-center py-12">
              <FileSpreadsheet className="w-12 h-12 text-text-muted mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-primary mb-2">
                Nenhuma transportadora cadastrada
              </h3>
              <p className="text-sm text-text-muted mb-4">
                Faca upload de uma tabela de precos CSV para comecar
              </p>
              <Button asChild>
                <Link href="/ferramentas/ativos/transportadoras/upload">
                  <Upload className="w-4 h-4 mr-2" />
                  Upload CSV
                </Link>
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">
                      Transportadora
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">
                      Versao
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">
                      Rotas
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">
                      Ultimo Upload
                    </th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-text-muted">
                      Acoes
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {carriers.map((carrier) => (
                    <tr
                      key={carrier.carrier_id}
                      className="border-b border-border/50 hover:bg-white/5 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                            <Truck className="w-4 h-4 text-blue-400" />
                          </div>
                          <div>
                            <p className="font-medium text-text-primary">
                              {carrier.display_name || carrier.carrier_name}
                            </p>
                            <p className="text-xs text-text-muted">
                              ID: {carrier.carrier_id}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        {carrier.is_active ? (
                          <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            Ativa
                          </Badge>
                        ) : (
                          <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                            <XCircle className="w-3 h-3 mr-1" />
                            Inativa
                          </Badge>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-text-primary">
                          v{carrier.current_version}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-text-primary">
                          {carrier.total_routes || 0}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1 text-sm text-text-muted">
                          <Calendar className="w-3 h-3" />
                          {formatDate(carrier.last_upload_at)}
                        </div>
                        {carrier.last_upload_by && (
                          <div className="flex items-center gap-1 text-xs text-text-muted mt-1">
                            <User className="w-3 h-3" />
                            {carrier.last_upload_by}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            asChild
                          >
                            <Link href={`/ferramentas/ativos/transportadoras/upload?carrier=${carrier.carrier_id}`}>
                              <Upload className="w-4 h-4" />
                            </Link>
                          </Button>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={deletingId === carrier.carrier_id}
                              >
                                {deletingId === carrier.carrier_id ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <Settings className="w-4 h-4" />
                                )}
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                className="text-red-400 focus:text-red-400"
                                onClick={() => handleDelete(carrier.carrier_id, carrier.display_name || carrier.carrier_name)}
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                Excluir Transportadora
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCardContent>
      </GlassCard>

      {/* Info Card */}
      <GlassCard>
        <GlassCardContent className="py-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center flex-shrink-0">
              <FileSpreadsheet className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-sm">
              <p className="font-medium text-text-primary mb-1">
                Como funciona o upload de tabelas
              </p>
              <p className="text-text-muted">
                1. Faca upload de um arquivo CSV com a tabela de precos da transportadora.
                <br />
                2. Nossa IA detecta automaticamente a estrutura da tabela (colunas de preco, UF, zona, etc).
                <br />
                3. Confirme o mapeamento detectado e a tabela sera importada.
                <br />
                4. Os precos estarao disponiveis imediatamente nas cotacoes.
              </p>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>
    </div>
  );
}
