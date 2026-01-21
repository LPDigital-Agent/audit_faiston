'use client';

// =============================================================================
// Asset List Page - SGA Inventory Module
// =============================================================================
// Complete asset listing with search, filters, pagination, and export.
// =============================================================================

import { useState, useMemo } from 'react';
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
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  Package,
  Search,
  Filter,
  Download,
  ChevronRight,
  ChevronLeft,
  RefreshCw,
  MapPin,
  Calendar,
} from 'lucide-react';
import { useAssets, useAssetManagement } from '@/hooks/ativos';
import {
  SGA_STATUS_LABELS,
  SGA_STATUS_COLORS,
} from '@/lib/ativos/constants';
import type { SGAAssetStatus } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface FilterState {
  status: SGAAssetStatus | 'all';
  location: string;
  project: string;
}

// =============================================================================
// Page Component
// =============================================================================

export default function AssetListPage() {
  const { assets, isLoading, refetch } = useAssets();
  const { locations, projects } = useAssetManagement();

  // Local state
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState<FilterState>({
    status: 'all',
    location: '',
    project: '',
  });
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Filter assets
  const filteredAssets = useMemo(() => {
    return assets.filter((asset) => {
      // Search filter
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        const matchesSearch =
          asset.serial_number?.toLowerCase().includes(term) ||
          asset.part_number_id?.toLowerCase().includes(term) ||
          asset.id.toLowerCase().includes(term);
        if (!matchesSearch) return false;
      }

      // Status filter
      if (filters.status !== 'all' && asset.status !== filters.status) {
        return false;
      }

      // Location filter
      if (filters.location && asset.location_id !== filters.location) {
        return false;
      }

      // Project filter
      if (filters.project && asset.project_id !== filters.project) {
        return false;
      }

      return true;
    });
  }, [assets, searchTerm, filters]);

  // Pagination
  const totalPages = Math.ceil(filteredAssets.length / pageSize);
  const paginatedAssets = filteredAssets.slice(
    (page - 1) * pageSize,
    page * pageSize
  );

  // Status counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: assets.length };
    assets.forEach((asset) => {
      counts[asset.status] = (counts[asset.status] || 0) + 1;
    });
    return counts;
  }, [assets]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            Lista de Ativos
          </h1>
          <p className="text-sm text-text-muted mt-1">
            {filteredAssets.length} ativos encontrados
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Atualizar
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Filters Bar */}
      <GlassCard className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              placeholder="Buscar por serial, part number ou ID..."
              className="pl-10 bg-white/5 border-border"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <div className="flex gap-2">
            <select
              className="px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
              value={filters.status}
              onChange={(e) => {
                setFilters({ ...filters, status: e.target.value as SGAAssetStatus | 'all' });
                setPage(1);
              }}
            >
              <option value="all">Todos os Status</option>
              <option value="DISPONIVEL">Disponível</option>
              <option value="RESERVADO">Reservado</option>
              <option value="EM_CAMPO">Em Campo</option>
              <option value="MANUTENCAO">Manutenção</option>
              <option value="DESCARTADO">Descartado</option>
            </select>
          </div>
        </div>

        {/* Quick Status Filters */}
        <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
          <Badge
            variant="outline"
            className={`cursor-pointer whitespace-nowrap ${
              filters.status === 'all' ? 'bg-blue-mid/20 border-blue-mid' : 'hover:bg-white/10'
            }`}
            onClick={() => setFilters({ ...filters, status: 'all' })}
          >
            Todos ({statusCounts.all || 0})
          </Badge>
          {(['AVAILABLE', 'RESERVED', 'WITH_CUSTOMER', 'IN_REPAIR'] as SGAAssetStatus[]).map((status) => (
            <Badge
              key={status}
              variant="outline"
              className={`cursor-pointer whitespace-nowrap ${
                filters.status === status
                  ? SGA_STATUS_COLORS[status]
                  : 'hover:bg-white/10'
              }`}
              onClick={() => setFilters({ ...filters, status })}
            >
              {SGA_STATUS_LABELS[status]} ({statusCounts[status] || 0})
            </Badge>
          ))}
        </div>
      </GlassCard>

      {/* Asset Table */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-blue-light" />
              <GlassCardTitle>Ativos</GlassCardTitle>
            </div>
            <Badge variant="outline">
              {paginatedAssets.length} de {filteredAssets.length}
            </Badge>
          </div>
        </GlassCardHeader>

        {/* Table Header */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wider">
          <div className="col-span-3">Serial / ID</div>
          <div className="col-span-3">Part Number</div>
          <div className="col-span-2">Local</div>
          <div className="col-span-2">Status</div>
          <div className="col-span-2 text-right">Ações</div>
        </div>

        {/* Table Body */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
          </div>
        ) : paginatedAssets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Package className="w-12 h-12 text-text-muted mb-3" />
            <p className="text-sm text-text-muted">
              {searchTerm || filters.status !== 'all'
                ? 'Nenhum ativo encontrado com os filtros aplicados'
                : 'Nenhum ativo cadastrado'}
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-[600px]">
            <div className="divide-y divide-border">
              {paginatedAssets.map((asset, index) => (
                <motion.div
                  key={asset.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                >
                  <Link href={`/ferramentas/ativos/estoque/${asset.id}`}>
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 px-4 py-4 hover:bg-white/5 transition-colors cursor-pointer items-center">
                      {/* Serial/ID */}
                      <div className="col-span-3 flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-blue-mid/20 flex items-center justify-center shrink-0">
                          <Package className="w-5 h-5 text-blue-light" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-text-primary truncate">
                            {asset.serial_number || 'Sem serial'}
                          </p>
                          <p className="text-xs text-text-muted truncate">
                            {asset.id}
                          </p>
                        </div>
                      </div>

                      {/* Part Number */}
                      <div className="col-span-3">
                        <p className="text-sm text-text-primary truncate">
                          {asset.part_number_id}
                        </p>
                      </div>

                      {/* Location */}
                      <div className="col-span-2 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-text-muted" />
                        <p className="text-sm text-text-muted truncate">
                          {asset.location_id || 'Não definido'}
                        </p>
                      </div>

                      {/* Status */}
                      <div className="col-span-2">
                        <Badge className={SGA_STATUS_COLORS[asset.status] || 'bg-gray-500/20'}>
                          {SGA_STATUS_LABELS[asset.status] || asset.status}
                        </Badge>
                      </div>

                      {/* Actions */}
                      <div className="col-span-2 flex items-center justify-end">
                        <ChevronRight className="w-4 h-4 text-text-muted" />
                      </div>
                    </div>
                  </Link>
                </motion.div>
              ))}
            </div>
          </ScrollArea>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-border">
            <p className="text-sm text-text-muted">
              Página {page} de {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="w-4 h-4" />
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
              >
                Próximo
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </GlassCard>
    </div>
  );
}
