// =============================================================================
// NEXO AI Panel - Faiston Academy
// =============================================================================
// AI tutoring chat panel using RAG with episode transcription as context.
// Connects to AgentCore backend for real-time Q&A based on lesson content.
// =============================================================================

'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Sparkles, User, AlertCircle, Loader2 } from 'lucide-react';
import { MarkdownContent } from '@/components/ui/markdown-content';
import { motion, AnimatePresence } from 'framer-motion';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useNexoAIChatMutation } from '@/hooks/academy/useNexoAI';
import { ACADEMY_STORAGE_KEYS } from '@/lib/academy/constants';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface NexoAIPanelProps {
  courseId: string;
  episodeId: string;
  episodeTitle: string;
  transcription?: string; // Optional - if provided, use directly; otherwise fetch from file
}

// Get transcription path based on course/episode
function getTranscriptionPath(courseId: string, episodeId: string): string {
  return `/transcriptions/course-${courseId}/ep${episodeId}.txt`;
}

// localStorage key for conversation history
function getStorageKey(courseId: string, episodeId: string): string {
  return `${ACADEMY_STORAGE_KEYS.NOTES_PREFIX}nexo_${courseId}_${episodeId}`;
}

// Gemini conversation format (internal use only)
interface GeminiMessage {
  role: 'user' | 'model';
  parts: { text: string }[];
}

// Convert UI messages to Gemini conversation format
function toGeminiHistory(messages: ChatMessage[]): GeminiMessage[] {
  // Skip the welcome message (first one) and convert
  return messages.slice(1).map((msg) => ({
    role: msg.role === 'user' ? 'user' : 'model',
    parts: [{ text: msg.content }],
  }));
}

export function NexoAIPanel({
  courseId,
  episodeId,
  episodeTitle,
  transcription: providedTranscription,
}: NexoAIPanelProps) {
  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [transcription, setTranscription] = useState<string>(providedTranscription || '');
  const [transcriptionLoading, setTranscriptionLoading] = useState(!providedTranscription);
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null);
  const [input, setInput] = useState('');

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // API hook
  const { mutateAsync: askNexo, isPending: isTyping } = useNexoAIChatMutation();

  // Generate welcome message based on episode
  const getWelcomeMessage = useCallback((): ChatMessage => {
    return {
      id: 'welcome',
      role: 'assistant',
      content: `Ola! 👋 Sou o NEXO, seu tutor de IA.\n\nEstou aqui para te ajudar com duvidas sobre **${episodeTitle}**.\n\nPode me perguntar qualquer coisa sobre o conteudo desta aula!`,
      timestamp: new Date(),
    };
  }, [episodeTitle]);

  // Load transcription when episode changes (only if not provided)
  useEffect(() => {
    if (providedTranscription) {
      setTranscription(providedTranscription);
      setTranscriptionLoading(false);
      return;
    }

    const loadTranscription = async () => {
      setTranscriptionLoading(true);
      setTranscriptionError(null);

      try {
        const path = getTranscriptionPath(courseId, episodeId);
        const response = await fetch(path);

        if (!response.ok) {
          throw new Error(`Transcription not found for episode ${episodeId}`);
        }

        const text = await response.text();

        // Validate it's actual transcription text (not HTML)
        if (text.includes('<!DOCTYPE') || text.includes('<html')) {
          throw new Error('Invalid transcription format');
        }

        setTranscription(text);
      } catch (err) {
        console.error('Failed to load transcription:', err);
        setTranscriptionError(
          'Nao foi possivel carregar a transcricao. NEXO funcionara com conhecimento limitado.'
        );
        setTranscription(''); // Allow chat to continue without transcription
      } finally {
        setTranscriptionLoading(false);
      }
    };

    loadTranscription();
  }, [courseId, episodeId, providedTranscription]);

  // Load conversation history from localStorage or initialize
  useEffect(() => {
    const key = getStorageKey(courseId, episodeId);
    const saved = localStorage.getItem(key);

    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Convert timestamps back to Date objects
        const restored = parsed.map((msg: ChatMessage) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }));
        setMessages(restored);
      } catch {
        // Invalid saved data, start fresh
        setMessages([getWelcomeMessage()]);
      }
    } else {
      setMessages([getWelcomeMessage()]);
    }
  }, [courseId, episodeId, getWelcomeMessage]);

  // Save conversation history to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      const key = getStorageKey(courseId, episodeId);
      localStorage.setItem(key, JSON.stringify(messages));
    }
  }, [messages, courseId, episodeId]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      // ScrollArea uses Radix UI which has a nested Viewport element
      const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, [messages, isTyping]);

  // Handle sending a message
  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const question = input.trim();
    setInput('');

    try {
      // Build conversation history for API (excluding welcome message)
      const history = toGeminiHistory([...messages, userMessage]);

      // Call NEXO AI backend
      const response = await askNexo({
        question,
        transcription:
          transcription ||
          'Transcricao nao disponivel para este episodio. Por favor, assista ao video e tente novamente.',
        episodeTitle,
        conversationHistory: history.slice(0, -1), // Exclude current question (it's sent separately)
      });

      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      console.error('NEXO AI error:', err);

      // Add error message
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          'Desculpe, tive um problema ao processar sua pergunta. Por favor, tente novamente. 🙏',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Clear conversation
  const handleClearHistory = () => {
    setMessages([getWelcomeMessage()]);
    const key = getStorageKey(courseId, episodeId);
    localStorage.removeItem(key);
  };

  return (
    <div className="h-full flex flex-col bg-black/20">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)]/20 to-[var(--faiston-blue-mid,#2226C0)]/20 flex items-center justify-center border border-[var(--faiston-magenta-mid,#C31B8C)]/20">
              <Sparkles className="w-5 h-5 text-[var(--faiston-magenta-mid,#C31B8C)]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">NEXO AI</h3>
              <p className="text-xs text-white/40">
                {transcriptionLoading ? 'Carregando...' : episodeTitle}
              </p>
            </div>
          </div>
          {messages.length > 1 && (
            <button
              onClick={handleClearHistory}
              className="text-xs text-white/40 hover:text-[var(--faiston-magenta-mid,#C31B8C)] transition-colors"
              title="Limpar conversa"
            >
              Limpar
            </button>
          )}
        </div>
      </div>

      {/* Transcription Error Banner */}
      {transcriptionError && (
        <div className="px-4 py-2 bg-yellow-500/10 border-b border-yellow-500/20 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-yellow-500" />
          <p className="text-xs text-yellow-500">{transcriptionError}</p>
        </div>
      )}

      {/* Messages */}
      <ScrollArea className="flex-1 p-4" ref={scrollRef}>
        <div className="space-y-4">
          <AnimatePresence initial={false}>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center ${
                    message.role === 'assistant'
                      ? 'bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)]'
                      : 'bg-white/10'
                  }`}
                >
                  {message.role === 'assistant' ? (
                    <Sparkles className="w-4 h-4 text-white" />
                  ) : (
                    <User className="w-4 h-4 text-white/70" />
                  )}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
                    message.role === 'assistant'
                      ? 'bg-white/10 rounded-tl-sm'
                      : 'bg-[var(--faiston-magenta-mid,#C31B8C)]/20 rounded-tr-sm'
                  }`}
                >
                  <MarkdownContent
                    content={message.content}
                    className="text-left text-sm prose-p:text-sm prose-p:my-1"
                  />
                  <p className="text-[10px] text-white/30 mt-1">
                    {message.timestamp.toLocaleTimeString('pt-BR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Typing indicator */}
          {isTyping && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3"
            >
              <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)]">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-white/50 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-white/50 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-white/50 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="p-4 border-t border-white/5">
        <div className="flex gap-2">
          <Input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              transcriptionLoading ? 'Carregando transcricao...' : 'Pergunte sobre a aula...'
            }
            className="flex-1 bg-white/[0.03] border-white/10 text-white placeholder:text-white/20 rounded-xl focus:border-[var(--faiston-magenta-mid,#C31B8C)]/50 focus:ring-1 focus:ring-[var(--faiston-magenta-mid,#C31B8C)]/20"
            disabled={isTyping || transcriptionLoading}
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isTyping || transcriptionLoading}
            className="bg-gradient-to-r from-[var(--faiston-magenta-mid,#C31B8C)] to-[var(--faiston-blue-mid,#2226C0)] hover:from-[var(--faiston-magenta-mid,#C31B8C)]/80 hover:to-[var(--faiston-blue-mid,#2226C0)]/80 text-white border-0 rounded-xl"
          >
            {isTyping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
        <p className="text-[10px] text-white/30 mt-2 text-center">
          NEXO responde com base no conteudo desta aula especifica.
        </p>
      </div>
    </div>
  );
}
