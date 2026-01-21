'use client';

// =============================================================================
// Nexo Assistant Floating Action Button - Gestão de Ativos
// =============================================================================
// Floating AI assistant icon with Apple TV-style frosted dark glass chat panel.
// Uses NexoEstoqueContext for chat state management.
// =============================================================================

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Image from 'next/image';
import {
  Send,
  X,
  Trash2,
  Loader2,
  MessageSquare,
  Package,
  MapPin,
  RotateCcw,
  CheckSquare,
  AlertTriangle,
  Activity,
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
import { KBCitationsList } from './estoque/nexo/KBCitationCard';

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
// Keywords for Knowledge Base routing
// =============================================================================

const KB_QUERY_KEYWORDS = [
  'manual', 'datasheet', 'especificacao', 'especificações', 'documentacao',
  'documentação', 'instalacao', 'instalação', 'configuracao', 'configuração',
  'firmware', 'driver', 'guia', 'tutorial',
];

function isKBQuery(question: string): boolean {
  const lower = question.toLowerCase();
  return KB_QUERY_KEYWORDS.some(keyword => lower.includes(keyword));
}

// =============================================================================
// NexoAssistantFAB Component
// =============================================================================

export function NexoAssistantFAB() {
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

  const isBusy = isLoading || isQueryingKB;

  // Handle send - routes to KB or general chat
  const handleSend = useCallback(async () => {
    if (!input.trim() || isBusy) return;

    const question = input.trim();
    setInput('');

    try {
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
      {/* Floating Avatar Button */}
      <motion.button
        className="fixed bottom-6 right-6 z-50 flex items-center justify-center w-16 h-16 rounded-full overflow-hidden shadow-2xl ring-2 ring-white/10 hover:ring-white/20 transition-all"
        style={{
          background: 'linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
        whileHover={{ scale: 1.08, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
        whileTap={{ scale: 0.95 }}
        onClick={togglePanel}
        aria-label="Abrir Assistente NEXO"
      >
        <AnimatePresence mode="wait">
          {isPanelOpen ? (
            <motion.div
              key="close"
              initial={{ rotate: -90, opacity: 0 }}
              animate={{ rotate: 0, opacity: 1 }}
              exit={{ rotate: 90, opacity: 0 }}
              className="flex items-center justify-center w-full h-full bg-white/5"
            >
              <X className="w-6 h-6 text-white/90" />
            </motion.div>
          ) : (
            <motion.div
              key="avatar"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.8, opacity: 0 }}
              className="relative w-full h-full"
            >
              <Image
                src="/Avatars/nexo-avatar.png"
                alt="NEXO Assistant"
                fill
                className="object-cover"
                priority
              />
              {/* Online indicator */}
              <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full border-2 border-faiston-bg" />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.button>

      {/* Chat Panel - Apple TV Frosted Dark Glass */}
      <AnimatePresence>
        {isPanelOpen && (
          <motion.div
            className="fixed bottom-28 right-6 z-50 w-[400px] max-w-[calc(100vw-3rem)] overflow-hidden rounded-3xl"
            style={{
              background: 'linear-gradient(180deg, rgba(30, 30, 35, 0.85) 0%, rgba(20, 20, 25, 0.92) 100%)',
              backdropFilter: 'blur(40px) saturate(180%)',
              WebkitBackdropFilter: 'blur(40px) saturate(180%)',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
            }}
            initial={{ opacity: 0, y: 30, scale: 0.92 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.92 }}
            transition={{ type: 'spring', damping: 28, stiffness: 320 }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.05) 0%, transparent 100%)',
              }}
            >
              <div className="flex items-center gap-3">
                <div className="relative w-11 h-11 rounded-full overflow-hidden ring-2 ring-white/10">
                  <Image
                    src="/Avatars/nexo-avatar.png"
                    alt="NEXO"
                    fill
                    className="object-cover"
                  />
                </div>
                <div>
                  <h3 className="font-semibold text-white/95 text-[15px] tracking-tight">
                    NEXO
                  </h3>
                  <p className="text-[12px] text-white/50 font-light">
                    Assistente de Ativos
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={clearChat}
                  className="text-white/40 hover:text-white/80 hover:bg-white/5 rounded-full w-9 h-9"
                  title="Limpar conversa"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={togglePanel}
                  className="text-white/40 hover:text-white/80 hover:bg-white/5 rounded-full w-9 h-9"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Quick Actions (when no messages) */}
            {messages.length === 0 && (
              <div
                className="px-5 py-4"
                style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}
              >
                <p className="text-[11px] text-white/40 uppercase tracking-wider mb-3 font-medium">
                  Ações rápidas
                </p>
                <div className="flex flex-wrap gap-2">
                  {quickActions.slice(0, 4).map((action) => {
                    const IconComponent = action.icon ? iconMap[action.icon] : MessageSquare;
                    return (
                      <button
                        key={action.id}
                        onClick={() => handleQuickAction(action)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[12px] font-medium text-white/70 hover:text-white/95 transition-all"
                        style={{
                          background: 'rgba(255, 255, 255, 0.06)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                        }}
                      >
                        <IconComponent className="w-3.5 h-3.5" />
                        {action.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Messages */}
            <ScrollArea className="h-80" ref={scrollRef}>
              <div className="px-5 py-4 space-y-4">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10">
                    <div className="relative w-20 h-20 rounded-full overflow-hidden mb-4 ring-2 ring-white/10">
                      <Image
                        src="/Avatars/nexo-avatar.png"
                        alt="NEXO"
                        fill
                        className="object-cover opacity-80"
                      />
                    </div>
                    <p className="text-[14px] text-white/70 text-center font-light">
                      Olá! Sou o NEXO, seu assistente
                      <br />
                      de Gestão de Ativos.
                    </p>
                    <p className="text-[12px] text-white/40 text-center mt-2">
                      Como posso ajudar?
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
                          msg.role === 'user'
                            ? 'text-white/95'
                            : 'text-white/90'
                        }`}
                        style={
                          msg.role === 'user'
                            ? {
                                background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.7) 0%, rgba(99, 102, 241, 0.7) 100%)',
                              }
                            : {
                                background: 'rgba(255, 255, 255, 0.06)',
                                border: '1px solid rgba(255, 255, 255, 0.06)',
                              }
                        }
                      >
                        {msg.role === 'assistant' ? (
                          <MarkdownContent
                            content={msg.content}
                            className="text-[13px] prose-sm prose-invert prose-p:leading-relaxed"
                          />
                        ) : (
                          <p className="text-[13px] leading-relaxed">{msg.content}</p>
                        )}
                      </div>

                      {/* Citations */}
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
                    <div
                      className="rounded-2xl px-4 py-3"
                      style={{
                        background: 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
                        <span className="text-[13px] text-white/60">
                          {isQueryingKB ? 'Consultando documentação...' : 'Pensando...'}
                        </span>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Error */}
                {error && (
                  <div
                    className="flex items-center gap-2 p-3 rounded-xl"
                    style={{
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid rgba(239, 68, 68, 0.2)',
                    }}
                  >
                    <AlertTriangle className="w-4 h-4 text-red-400" />
                    <p className="text-[12px] text-red-300">{error}</p>
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Suggestions */}
            {suggestions.length > 0 && (
              <div className="px-5 pb-3">
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.slice(0, 3).map((suggestion, idx) => (
                    <Badge
                      key={idx}
                      variant="outline"
                      className="cursor-pointer text-[11px] text-white/60 hover:text-white/90 border-white/10 hover:bg-white/5 transition-colors"
                      onClick={() => handleSuggestion(suggestion)}
                    >
                      {suggestion}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Input */}
            <div
              className="px-5 py-4"
              style={{
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                background: 'linear-gradient(0deg, rgba(0, 0, 0, 0.2) 0%, transparent 100%)',
              }}
            >
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  type="text"
                  placeholder="Pergunte sobre ativos..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyPress}
                  disabled={isBusy}
                  className="flex-1 h-11 rounded-xl text-[13px] text-white/90 placeholder:text-white/30 border-0"
                  style={{
                    background: 'rgba(255, 255, 255, 0.06)',
                  }}
                />
                <Button
                  onClick={handleSend}
                  disabled={!input.trim() || isBusy}
                  className="h-11 w-11 rounded-xl p-0 transition-all"
                  style={{
                    background: input.trim() && !isBusy
                      ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.8) 0%, rgba(99, 102, 241, 0.8) 100%)'
                      : 'rgba(255, 255, 255, 0.06)',
                  }}
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

export default NexoAssistantFAB;
