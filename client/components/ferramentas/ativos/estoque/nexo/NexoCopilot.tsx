'use client';

// =============================================================================
// NEXO Copilot - SGA Inventory AI Assistant Panel
// =============================================================================
// Floating AI chat panel for inventory queries and quick actions.
// Uses the NexoEstoqueContext for state management.
// =============================================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  Send,
  X,
  Trash2,
  Package,
  MapPin,
  RotateCcw,
  CheckSquare,
  AlertTriangle,
  Activity,
  Loader2,
  MessageSquare,
  FileText,
  BookOpen,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { MarkdownContent } from '@/components/ui/markdown-content';
import { useNexoEstoque } from '@/contexts/ativos';
import type { QuickAction } from '@/contexts/ativos/NexoEstoqueContext';
import { KBCitationsList } from './KBCitationCard';
import { useInventoryOperations } from '@/contexts/ativos/InventoryOperationsContext';

// =============================================================================
// Icon Map for Quick Actions
// =============================================================================

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Package,
  MapPin,
  RotateCcw,
  CheckSquare,
  AlertTriangle,
  Activity,
  FileText,
  BookOpen,
};

// =============================================================================
// NexoCopilot Component
// =============================================================================

// Keywords that indicate an equipment documentation query
const KB_QUERY_KEYWORDS = [
  'manual', 'datasheet', 'especificacao', 'especificações', 'documentacao',
  'documentação', 'instalacao', 'instalação', 'configuracao', 'configuração',
  'firmware', 'driver', 'guia', 'tutorial',
];

/**
 * Check if a question is likely about equipment documentation.
 */
function isKBQuery(question: string): boolean {
  const lower = question.toLowerCase();
  return KB_QUERY_KEYWORDS.some(keyword => lower.includes(keyword));
}

export function NexoCopilot() {
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    clearChat,
    queryKB,
    isQueryingKB,
    suggestions,
    quickActions,
    isPanelOpen,
    togglePanel,
  } = useNexoEstoque();

  // Background job tracking for fire-and-forget imports
  const { activeJobs, hasActiveImportJobs, getActiveJobCount } = useInventoryOperations();
  const hasBackgroundWork = hasActiveImportJobs();
  const activeJobCount = getActiveJobCount();

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when panel opens
  useEffect(() => {
    if (isPanelOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isPanelOpen]);

  // Combined loading state
  const isBusy = isLoading || isQueryingKB;

  // Handle send - routes to KB or general chat based on question content
  const handleSend = useCallback(async () => {
    if (!input.trim() || isBusy) return;

    const question = input.trim();
    setInput('');

    try {
      // Route documentation questions to Knowledge Base
      if (isKBQuery(question)) {
        await queryKB(question);
      } else {
        await sendMessage(question);
      }
    } catch {
      // Error handled by context
    }
  }, [input, isBusy, sendMessage, queryKB]);

  // Handle quick action
  const handleQuickAction = useCallback((action: QuickAction) => {
    setInput(action.query);
    inputRef.current?.focus();
  }, []);

  // Handle suggestion click
  const handleSuggestion = useCallback((suggestion: string) => {
    setInput(suggestion);
    inputRef.current?.focus();
  }, []);

  // Handle key press
  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <>
      {/* Floating Button */}
      <motion.button
        className="fixed bottom-6 right-6 z-50 flex items-center justify-center w-14 h-14 rounded-full bg-gradient-to-r from-magenta-mid to-blue-mid text-white shadow-lg hover:shadow-xl transition-shadow"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={togglePanel}
        aria-label="Abrir NEXO Copilot"
      >
        <AnimatePresence mode="wait">
          {isPanelOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
            >
              <X className="w-6 h-6" />
            </motion.div>
          ) : (
            <motion.div
              key="open"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
            >
              <Sparkles className="w-6 h-6" />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Background job indicator badge */}
        {hasBackgroundWork && (
          <motion.div
            className="absolute -top-1 -right-1 w-5 h-5 bg-cyan-500 rounded-full flex items-center justify-center border-2 border-background"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          >
            <span className="text-[10px] font-bold text-white">{activeJobCount}</span>
          </motion.div>
        )}
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {isPanelOpen && (
          <motion.div
            className="fixed bottom-24 right-6 z-50 w-96 max-w-[calc(100vw-3rem)] bg-background/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-border overflow-hidden"
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-border bg-gradient-to-r from-magenta-dark/20 to-blue-dark/20">
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-r from-magenta-mid to-blue-mid">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold text-text-primary">NEXO</h3>
                  {/* Background job indicator or default subtitle */}
                  {hasBackgroundWork ? (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex items-center gap-1.5"
                    >
                      <Loader2 className="w-3 h-3 text-cyan-400 animate-spin" />
                      <span className="text-xs text-cyan-400">
                        Processando em segundo plano...
                      </span>
                    </motion.div>
                  ) : (
                    <p className="text-xs text-text-muted">Assistente de Estoque</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={clearChat}
                  className="text-text-muted hover:text-text-primary"
                  title="Limpar conversa"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={togglePanel}
                  className="text-text-muted hover:text-text-primary"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Quick Actions (when no messages) */}
            {messages.length === 0 && (
              <div className="p-4 border-b border-border">
                <p className="text-xs text-text-muted mb-2">Acoes rapidas:</p>
                <div className="flex flex-wrap gap-2">
                  {quickActions.slice(0, 4).map((action) => {
                    const IconComponent = action.icon ? iconMap[action.icon] : MessageSquare;
                    return (
                      <Button
                        key={action.id}
                        variant="outline"
                        size="sm"
                        className="text-xs"
                        onClick={() => handleQuickAction(action)}
                      >
                        <IconComponent className="w-3 h-3 mr-1" />
                        {action.label}
                      </Button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Messages */}
            <ScrollArea className="h-80" ref={scrollRef}>
              <div className="p-4 space-y-4">
                {messages.length === 0 ? (
                  <div className="text-center py-8">
                    <Sparkles className="w-12 h-12 text-text-muted mx-auto mb-3" />
                    <p className="text-sm text-text-muted">
                      Ola! Como posso ajudar com o estoque?
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-xl px-4 py-2 ${
                          msg.role === 'user'
                            ? 'bg-gradient-to-r from-magenta-mid to-blue-mid text-white'
                            : 'bg-white/5 border border-border text-text-primary'
                        }`}
                      >
                        {msg.role === 'assistant' ? (
                          <MarkdownContent
                            content={msg.content}
                            className="text-sm prose-sm"
                          />
                        ) : (
                          <p className="text-sm">{msg.content}</p>
                        )}
                      </div>

                      {/* Citations from Knowledge Base */}
                      {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                        <div className="max-w-[85%] mt-2">
                          <KBCitationsList
                            citations={msg.citations}
                            maxVisible={3}
                          />
                        </div>
                      )}
                    </motion.div>
                  ))
                )}

                {/* Loading indicator */}
                {isBusy && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-start"
                  >
                    <div className="bg-white/5 border border-border rounded-xl px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-magenta-mid" />
                        <span className="text-sm text-text-muted">
                          {isQueryingKB ? 'Consultando documentacao...' : 'Pensando...'}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Error */}
                {error && (
                  <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    <p className="text-xs text-red-400">{error}</p>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Suggestions */}
            {suggestions.length > 0 && (
              <div className="px-4 pb-2">
                <div className="flex flex-wrap gap-1">
                  {suggestions.slice(0, 3).map((suggestion, idx) => (
                    <Badge
                      key={idx}
                      variant="outline"
                      className="cursor-pointer hover:bg-white/10 text-xs"
                      onClick={() => handleSuggestion(suggestion)}
                    >
                      {suggestion}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Input */}
            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  type="text"
                  placeholder="Pergunte sobre estoque ou documentacao..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyPress}
                  disabled={isBusy}
                  className="flex-1 bg-white/5 border-border"
                />
                <Button
                  onClick={handleSend}
                  disabled={!input.trim() || isBusy}
                  className="bg-gradient-to-r from-magenta-mid to-blue-mid hover:opacity-90"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
