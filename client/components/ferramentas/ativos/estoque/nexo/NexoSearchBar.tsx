'use client';

// =============================================================================
// NEXO Search Bar - SGA Inventory Quick Search
// =============================================================================
// AI-powered search bar for quick inventory queries.
// Supports natural language and structured searches.
// =============================================================================

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Sparkles,
  Package,
  MapPin,
  Hash,
  Clock,
  X,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useNexoEstoque } from '@/contexts/ativos';

// =============================================================================
// Search Examples
// =============================================================================

const SEARCH_EXAMPLES = [
  { icon: Package, text: 'ONT-ZTE-F601', type: 'Part Number' },
  { icon: Hash, text: 'SN123456789', type: 'Serial' },
  { icon: MapPin, text: 'Almoxarifado SP', type: 'Local' },
  { icon: Clock, text: 'Ultimas entradas', type: 'Movimentacoes' },
];

// =============================================================================
// Types
// =============================================================================

interface NexoSearchBarProps {
  onSearch?: (query: string, results: unknown) => void;
  placeholder?: string;
  className?: string;
}

// =============================================================================
// Component
// =============================================================================

export function NexoSearchBar({
  onSearch,
  placeholder = 'Buscar ativos, seriais, locais...',
  className = '',
}: NexoSearchBarProps) {
  const { sendMessage, isLoading, togglePanel } = useNexoEstoque();

  const [query, setQuery] = useState('');
  const [isFocused, setIsFocused] = useState(false);
  const [showExamples, setShowExamples] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close examples on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowExamples(false);
        setIsFocused(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Handle search
  const handleSearch = useCallback(async () => {
    if (!query.trim() || isLoading) return;

    try {
      const result = await sendMessage(query.trim());
      if (onSearch) {
        onSearch(query.trim(), result);
      }
      setQuery('');
      setShowExamples(false);
    } catch {
      // Error handled by context
    }
  }, [query, isLoading, sendMessage, onSearch]);

  // Handle example click
  const handleExampleClick = useCallback((example: typeof SEARCH_EXAMPLES[0]) => {
    setQuery(example.text);
    setShowExamples(false);
    inputRef.current?.focus();
  }, []);

  // Handle key press
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    } else if (e.key === 'Escape') {
      setShowExamples(false);
      setQuery('');
      inputRef.current?.blur();
    }
  }, [handleSearch]);

  // Handle focus
  const handleFocus = useCallback(() => {
    setIsFocused(true);
    setShowExamples(true);
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Search Input */}
      <div
        className={`relative flex items-center gap-2 rounded-lg border transition-all ${
          isFocused
            ? 'border-magenta-mid bg-white/10 ring-2 ring-magenta-mid/20'
            : 'border-border bg-white/5 hover:border-border/80'
        }`}
      >
        {/* Search Icon / Sparkles */}
        <div className="pl-3">
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-magenta-mid animate-spin" />
          ) : isFocused ? (
            <Sparkles className="w-4 h-4 text-magenta-mid" />
          ) : (
            <Search className="w-4 h-4 text-text-muted" />
          )}
        </div>

        {/* Input */}
        <Input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          className="flex-1 border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-text-muted"
        />

        {/* Clear / Submit Buttons */}
        <div className="flex items-center gap-1 pr-2">
          {query && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-text-muted hover:text-text-primary"
              onClick={() => setQuery('')}
            >
              <X className="w-3 h-3" />
            </Button>
          )}
          <Button
            size="sm"
            disabled={!query.trim() || isLoading}
            onClick={handleSearch}
            className="h-7 px-2 bg-gradient-to-r from-magenta-mid to-blue-mid hover:opacity-90"
          >
            <ArrowRight className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Examples Dropdown */}
      <AnimatePresence>
        {showExamples && !query && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="absolute top-full left-0 right-0 mt-2 p-3 bg-background/95 backdrop-blur-xl rounded-lg border border-border shadow-xl z-50"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-text-muted">Exemplos de busca:</p>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs text-magenta-mid"
                onClick={() => {
                  setShowExamples(false);
                  togglePanel();
                }}
              >
                <Sparkles className="w-3 h-3 mr-1" />
                Conversar com NEXO
              </Button>
            </div>

            <div className="space-y-1">
              {SEARCH_EXAMPLES.map((example, idx) => {
                const IconComponent = example.icon;
                return (
                  <button
                    key={idx}
                    className="w-full flex items-center gap-3 p-2 rounded-md hover:bg-white/10 text-left transition-colors"
                    onClick={() => handleExampleClick(example)}
                  >
                    <IconComponent className="w-4 h-4 text-text-muted" />
                    <span className="flex-1 text-sm text-text-primary">{example.text}</span>
                    <Badge variant="outline" className="text-xs">
                      {example.type}
                    </Badge>
                  </button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
