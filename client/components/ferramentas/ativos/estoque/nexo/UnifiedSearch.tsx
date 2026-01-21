'use client';

// =============================================================================
// Unified Search - SGA Inventory Universal Search
// =============================================================================
// Combined search component that searches across assets, movements, locations,
// and uses AI for natural language queries.
// =============================================================================

import { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Package,
  MapPin,
  ArrowRightLeft,
  Hash,
  History,
  Sparkles,
  Loader2,
  X,
  Filter,
} from 'lucide-react';
import Link from 'next/link';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { useAssetManagement, useAssets, useMovements } from '@/hooks/ativos';
import type { SGAAsset, SGAMovement } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

type SearchCategory = 'all' | 'assets' | 'movements' | 'locations' | 'parts';

interface SearchResult {
  id: string;
  type: 'asset' | 'movement' | 'location' | 'part_number';
  title: string;
  subtitle: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeColor?: string;
}

interface UnifiedSearchProps {
  onSelect?: (result: SearchResult) => void;
  className?: string;
  showFilters?: boolean;
}

// =============================================================================
// Component
// =============================================================================

export function UnifiedSearch({
  onSelect,
  className = '',
  showFilters = true,
}: UnifiedSearchProps) {
  const { locations, partNumbers } = useAssetManagement();
  const { assets } = useAssets({});
  const { movements } = useMovements({});

  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<SearchCategory>('all');
  const [isOpen, setIsOpen] = useState(false);
  const [recentSearches] = useState<string[]>([
    'ONT-ZTE',
    'Almoxarifado',
    'SN12345',
  ]);

  // Filter results based on query and category
  const results = useMemo<SearchResult[]>(() => {
    if (!query.trim()) return [];

    const q = query.toLowerCase();
    const filtered: SearchResult[] = [];

    // Search assets
    if (category === 'all' || category === 'assets') {
      (assets || [])
        .filter(
          (a: SGAAsset) =>
            a.serial_number.toLowerCase().includes(q) ||
            a.part_number.toLowerCase().includes(q)
        )
        .slice(0, 5)
        .forEach((asset: SGAAsset) => {
          filtered.push({
            id: asset.id,
            type: 'asset',
            title: asset.serial_number,
            subtitle: `${asset.part_number} - ${asset.location_name || 'Sem local'}`,
            href: `/ferramentas/ativos/estoque/${asset.id}`,
            icon: Hash,
            badge: asset.status,
            badgeColor:
              asset.status === 'AVAILABLE'
                ? 'bg-green-500/20 text-green-400'
                : asset.status === 'RESERVED'
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-blue-500/20 text-blue-400',
          });
        });
    }

    // Search part numbers
    if (category === 'all' || category === 'parts') {
      partNumbers
        .filter(
          (pn) =>
            pn.part_number.toLowerCase().includes(q) ||
            pn.description.toLowerCase().includes(q)
        )
        .slice(0, 5)
        .forEach((pn) => {
          filtered.push({
            id: pn.id,
            type: 'part_number',
            title: pn.part_number,
            subtitle: pn.description,
            href: `/ferramentas/ativos/estoque/cadastros/part-numbers?pn=${pn.part_number}`,
            icon: Package,
            badge: pn.category,
          });
        });
    }

    // Search locations
    if (category === 'all' || category === 'locations') {
      locations
        .filter(
          (loc) =>
            loc.code.toLowerCase().includes(q) ||
            loc.name.toLowerCase().includes(q)
        )
        .slice(0, 5)
        .forEach((loc) => {
          filtered.push({
            id: loc.id,
            type: 'location',
            title: loc.code,
            subtitle: loc.name,
            href: `/ferramentas/ativos/estoque/cadastros/locais?loc=${loc.id}`,
            icon: MapPin,
            badge: loc.type,
          });
        });
    }

    // Search movements
    if (category === 'all' || category === 'movements') {
      (movements || [])
        .filter(
          (mov: SGAMovement) =>
            mov.part_number.toLowerCase().includes(q) ||
            mov.document_number?.toLowerCase().includes(q) ||
            mov.source_location_name?.toLowerCase().includes(q) ||
            mov.destination_location_name?.toLowerCase().includes(q)
        )
        .slice(0, 5)
        .forEach((mov: SGAMovement) => {
          filtered.push({
            id: mov.id,
            type: 'movement',
            title: `${mov.type} - ${mov.part_number}`,
            subtitle: `${mov.source_location_name || '-'} → ${mov.destination_location_name || '-'}`,
            href: `/ferramentas/ativos/estoque/movimentacoes?id=${mov.id}`,
            icon: ArrowRightLeft,
            badge: mov.type,
          });
        });
    }

    return filtered.slice(0, 15);
  }, [query, category, assets, partNumbers, locations, movements]);

  // Handle result click
  const handleResultClick = useCallback((result: SearchResult) => {
    if (onSelect) {
      onSelect(result);
    }
    setIsOpen(false);
    setQuery('');
  }, [onSelect]);

  // Handle recent search click
  const handleRecentClick = useCallback((search: string) => {
    setQuery(search);
  }, []);

  // Categories
  const categories: { value: SearchCategory; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { value: 'all', label: 'Todos', icon: Search },
    { value: 'assets', label: 'Ativos', icon: Hash },
    { value: 'parts', label: 'Part Numbers', icon: Package },
    { value: 'locations', label: 'Locais', icon: MapPin },
    { value: 'movements', label: 'Movimentacoes', icon: ArrowRightLeft },
  ];

  return (
    <GlassCard className={className}>
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-magenta-mid" />
          <GlassCardTitle>Busca Unificada</GlassCardTitle>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        {/* Search Input */}
        <div className="relative">
          <div className="relative flex items-center">
            <Search className="absolute left-3 w-4 h-4 text-text-muted" />
            <Input
              type="text"
              placeholder="Buscar ativos, seriais, locais, movimentacoes..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setIsOpen(true);
              }}
              onFocus={() => setIsOpen(true)}
              className="pl-10 pr-10 bg-white/5 border-border"
            />
            {query && (
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 h-6 w-6"
                onClick={() => {
                  setQuery('');
                  setIsOpen(false);
                }}
              >
                <X className="w-3 h-3" />
              </Button>
            )}
          </div>

          {/* Category Filters */}
          {showFilters && (
            <div className="flex gap-2 mt-3 overflow-x-auto pb-2">
              {categories.map((cat) => {
                const IconComponent = cat.icon;
                return (
                  <Button
                    key={cat.value}
                    variant={category === cat.value ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setCategory(cat.value)}
                    className={`text-xs whitespace-nowrap ${
                      category === cat.value
                        ? 'bg-magenta-mid/20 text-magenta-mid border-magenta-mid/30'
                        : ''
                    }`}
                  >
                    <IconComponent className="w-3 h-3 mr-1" />
                    {cat.label}
                  </Button>
                );
              })}
            </div>
          )}
        </div>

        {/* Results */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-4"
            >
              {query ? (
                results.length > 0 ? (
                  <ScrollArea className="max-h-64">
                    <div className="space-y-1">
                      {results.map((result) => {
                        const IconComponent = result.icon;
                        return (
                          <Link
                            key={`${result.type}-${result.id}`}
                            href={result.href}
                            onClick={() => handleResultClick(result)}
                            className="flex items-center gap-3 p-2 rounded-lg hover:bg-white/10 transition-colors"
                          >
                            <div className="flex items-center justify-center w-8 h-8 rounded-md bg-white/5">
                              <IconComponent className="w-4 h-4 text-text-muted" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-text-primary truncate">
                                {result.title}
                              </p>
                              <p className="text-xs text-text-muted truncate">
                                {result.subtitle}
                              </p>
                            </div>
                            {result.badge && (
                              <Badge
                                variant="outline"
                                className={`text-xs ${result.badgeColor || ''}`}
                              >
                                {result.badge}
                              </Badge>
                            )}
                          </Link>
                        );
                      })}
                    </div>
                  </ScrollArea>
                ) : (
                  <div className="py-8 text-center">
                    <Search className="w-10 h-10 text-text-muted mx-auto mb-2" />
                    <p className="text-sm text-text-muted">
                      Nenhum resultado para "{query}"
                    </p>
                  </div>
                )
              ) : (
                // Recent searches
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <History className="w-4 h-4 text-text-muted" />
                    <span className="text-xs text-text-muted">Buscas recentes:</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {recentSearches.map((search, idx) => (
                      <Badge
                        key={idx}
                        variant="outline"
                        className="cursor-pointer hover:bg-white/10"
                        onClick={() => handleRecentClick(search)}
                      >
                        {search}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </GlassCardContent>
    </GlassCard>
  );
}
