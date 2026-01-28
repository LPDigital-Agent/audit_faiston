'use client';

// =============================================================================
// Locations Page - SGA Inventory Module
// =============================================================================
// Location (warehouse/customer) management.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  MapPin,
  ArrowLeft,
  Search,
  Plus,
  RefreshCw,
  ChevronRight,
  Warehouse,
  Users,
  Lock,
  Check,
  X,
} from 'lucide-react';
import { useLocations } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function LocationsPage() {
  const {
    locations,
    isLoading,
    warehouseLocations,
    customerLocations,
    restrictedLocations,
    refresh,
  } = useLocations();

  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('all');

  const filteredLocations = locations.filter((loc) => {
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      if (!loc.code.toLowerCase().includes(term) && !loc.name.toLowerCase().includes(term)) {
        return false;
      }
    }
    if (filterType !== 'all' && loc.type !== filterType) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/cadastros">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Cadastros
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Locais
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Almoxarifados, clientes e pontos de entrega
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refresh()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Atualizar
          </Button>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Novo Local
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard className="p-4">
          <p className="text-2xl font-bold text-text-primary">
            {isLoading ? '...' : locations.length}
          </p>
          <p className="text-xs text-text-muted">Total de Locais</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Warehouse className="w-5 h-5 text-blue-light" />
            <p className="text-2xl font-bold text-blue-light">
              {isLoading ? '...' : warehouseLocations.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Armazéns</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-green-400" />
            <p className="text-2xl font-bold text-green-400">
              {isLoading ? '...' : customerLocations.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Clientes</p>
        </GlassCard>
        <GlassCard className="p-4">
          <div className="flex items-center gap-2">
            <Lock className="w-5 h-5 text-yellow-400" />
            <p className="text-2xl font-bold text-yellow-400">
              {isLoading ? '...' : restrictedLocations.length}
            </p>
          </div>
          <p className="text-xs text-text-muted">Restritos</p>
        </GlassCard>
      </div>

      {/* Filters */}
      <GlassCard className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              placeholder="Buscar por código ou nome..."
              className="pl-10 bg-white/5 border-border"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">Todos os Tipos</option>
            <option value="WAREHOUSE">Armazéns</option>
            <option value="CUSTOMER">Clientes</option>
            <option value="FIELD">Campo</option>
            <option value="TRANSIT">Trânsito</option>
          </select>
        </div>
      </GlassCard>

      {/* Locations List */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <MapPin className="w-4 h-4 text-green-400" />
              <GlassCardTitle>Locais</GlassCardTitle>
            </div>
            <Badge variant="outline">{filteredLocations.length} registros</Badge>
          </div>
        </GlassCardHeader>

        {/* Table Header */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-3 border-b border-border text-xs font-medium text-text-muted uppercase tracking-wider">
          <div className="col-span-2">Código</div>
          <div className="col-span-4">Nome</div>
          <div className="col-span-2">Tipo</div>
          <div className="col-span-2">Endereço</div>
          <div className="col-span-2 text-right">Status</div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-8 h-8 text-text-muted animate-spin" />
          </div>
        ) : filteredLocations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <MapPin className="w-12 h-12 text-text-muted mb-3" />
            <p className="text-sm text-text-muted">
              Nenhum local encontrado
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-[500px]">
            <div className="divide-y divide-border">
              {filteredLocations.map((location, index) => (
                <motion.div
                  key={location.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                  className="grid grid-cols-1 md:grid-cols-12 gap-4 px-4 py-4 hover:bg-white/5 transition-colors cursor-pointer items-center"
                >
                  <div className="col-span-2 flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                      location.type === 'WAREHOUSE' ? 'bg-blue-mid/20' :
                      location.type === 'CUSTOMER' ? 'bg-green-500/20' :
                      'bg-yellow-500/20'
                    }`}>
                      {location.type === 'WAREHOUSE' ? (
                        <Warehouse className="w-5 h-5 text-blue-light" />
                      ) : location.type === 'CUSTOMER' ? (
                        <Users className="w-5 h-5 text-green-400" />
                      ) : (
                        <MapPin className="w-5 h-5 text-yellow-400" />
                      )}
                    </div>
                    <p className="text-sm font-medium text-text-primary font-mono">
                      {location.code}
                    </p>
                  </div>

                  <div className="col-span-4">
                    <p className="text-sm text-text-primary truncate">
                      {location.name}
                    </p>
                  </div>

                  <div className="col-span-2">
                    <Badge variant="outline" className="text-xs">
                      {location.type === 'WAREHOUSE' ? 'Armazém' :
                       location.type === 'CUSTOMER' ? 'Cliente' :
                       location.type === 'TRANSIT' ? 'Trânsito' :
                       location.type === 'SHELF' ? 'Prateleira' :
                       location.type === 'BIN' ? 'Gaveta' :
                       location.type === 'VIRTUAL' ? 'Virtual' : location.type}
                    </Badge>
                    {location.is_restricted && (
                      <Badge variant="outline" className="text-xs ml-1 bg-yellow-500/20 text-yellow-400 border-yellow-500/30">
                        <Lock className="w-3 h-3" />
                      </Badge>
                    )}
                  </div>

                  <div className="col-span-2">
                    <p className="text-sm text-text-muted truncate">
                      {location.address || '-'}
                    </p>
                  </div>

                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {location.is_active ? (
                      <Badge className="bg-green-500/20 text-green-400 border-green-500/30">
                        <Check className="w-3 h-3 mr-1" />
                        Ativo
                      </Badge>
                    ) : (
                      <Badge className="bg-red-500/20 text-red-400 border-red-500/30">
                        <X className="w-3 h-3 mr-1" />
                        Inativo
                      </Badge>
                    )}
                    <ChevronRight className="w-4 h-4 text-text-muted" />
                  </div>
                </motion.div>
              ))}
            </div>
          </ScrollArea>
        )}
      </GlassCard>
    </div>
  );
}
