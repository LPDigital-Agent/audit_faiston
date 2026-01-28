// =============================================================================
// NEXO Estoque Context - SGA Inventory Module
// =============================================================================
// AI assistant context for inventory queries and natural language interactions.
// Manages chat history, suggestions, and contextual responses.
// =============================================================================

'use client';

import {
  createContext,
  useContext,
  useState,
  ReactNode,
  useCallback,
  useRef,
} from 'react';
import { nexoEstoqueChat, queryEquipmentDocs } from '@/services/sgaAgentcore';
import type { SGANexoChatResponse, KBCitation } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  data?: Record<string, unknown>;
  suggestions?: string[];
  citations?: KBCitation[];
}

interface NexoEstoqueContextType {
  // Chat state
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;

  // Actions
  sendMessage: (question: string, context?: Record<string, unknown>) => Promise<SGANexoChatResponse>;
  clearChat: () => void;

  // Knowledge Base query
  queryKB: (query: string, partNumber?: string) => Promise<void>;
  isQueryingKB: boolean;

  // Suggestions
  suggestions: string[];
  setSuggestions: (suggestions: string[]) => void;

  // Quick actions (commonly used queries)
  quickActions: QuickAction[];

  // Panel state
  isPanelOpen: boolean;
  setIsPanelOpen: (open: boolean) => void;
  togglePanel: () => void;
}

export interface QuickAction {
  id: string;
  label: string;
  query: string;
  icon?: string;
}

// =============================================================================
// Default Quick Actions
// =============================================================================

const DEFAULT_QUICK_ACTIONS: QuickAction[] = [
  {
    id: 'balance',
    label: 'Verificar saldo',
    query: 'Qual o saldo disponivel de {part_number}?',
    icon: 'Package',
  },
  {
    id: 'locate',
    label: 'Localizar serial',
    query: 'Onde esta o serial {serial}?',
    icon: 'MapPin',
  },
  {
    id: 'docs',
    label: 'Documentacao equipamento',
    query: 'Onde encontro o manual do {part_number}?',
    icon: 'FileText',
  },
  {
    id: 'pending',
    label: 'Reversas pendentes',
    query: 'Quais reversas estao pendentes?',
    icon: 'RotateCcw',
  },
  {
    id: 'tasks',
    label: 'Minhas tarefas',
    query: 'Quais tarefas preciso aprovar?',
    icon: 'CheckSquare',
  },
  {
    id: 'lowstock',
    label: 'Itens abaixo do minimo',
    query: 'Quais itens estao abaixo do estoque minimo?',
    icon: 'AlertTriangle',
  },
  {
    id: 'movements',
    label: 'Movimentacoes hoje',
    query: 'Quais movimentacoes foram feitas hoje?',
    icon: 'Activity',
  },
];

// =============================================================================
// Context
// =============================================================================

const NexoEstoqueContext = createContext<NexoEstoqueContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface NexoEstoqueProviderProps {
  children: ReactNode;
}

export function NexoEstoqueProvider({ children }: NexoEstoqueProviderProps) {
  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // KB query state
  const [isQueryingKB, setIsQueryingKB] = useState(false);

  // Suggestions state
  const [suggestions, setSuggestions] = useState<string[]>([]);

  // Panel state
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  // Abort controller ref for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate unique ID
  const generateId = () => `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  // Build conversation history for context
  const buildConversationHistory = useCallback(() => {
    return messages.slice(-10).map(msg => ({
      role: msg.role,
      content: msg.content,
    }));
  }, [messages]);

  // Send message to NEXO
  const sendMessage = useCallback(async (
    question: string,
    context?: Record<string, unknown>
  ): Promise<SGANexoChatResponse> => {
    // Cancel any pending request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Add user message
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    setIsLoading(true);
    setError(null);

    try {
      const result = await nexoEstoqueChat({
        question,
        context,
        conversation_history: buildConversationHistory(),
      });

      // Add assistant response
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: result.data.answer,
        timestamp: new Date().toISOString(),
        data: result.data.data,
        suggestions: result.data.suggestions,
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Update suggestions
      if (result.data.suggestions?.length) {
        setSuggestions(result.data.suggestions);
      }

      return result.data;
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        throw err;
      }

      const errorMessage = err instanceof Error ? err.message : 'Erro ao processar sua pergunta';
      setError(errorMessage);

      // Add error message
      const errorResponse: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: `Desculpe, ocorreu um erro: ${errorMessage}. Por favor, tente novamente.`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorResponse]);

      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [buildConversationHistory]);

  // Query Knowledge Base for equipment documentation
  const queryKB = useCallback(async (
    query: string,
    partNumber?: string
  ): Promise<void> => {
    // Add user message showing the KB query
    const userMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMessage]);

    setIsQueryingKB(true);
    setError(null);

    try {
      const result = await queryEquipmentDocs({
        query,
        part_number: partNumber,
        max_results: 5,
      });

      // Add assistant response with KB answer and citations
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: result.data.answer || 'Nenhuma informacao encontrada na base de conhecimento.',
        timestamp: new Date().toISOString(),
        citations: result.data.citations || [],
        data: { source: 'knowledge_base', query },
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Set follow-up suggestions
      setSuggestions([
        'Mais detalhes sobre este equipamento',
        'Como fazer a instalacao?',
        'Quais sao as especificacoes tecnicas?',
      ]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erro ao consultar base de conhecimento';
      setError(errorMessage);

      const errorResponse: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: `Nao foi possivel consultar a documentacao: ${errorMessage}`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorResponse]);
    } finally {
      setIsQueryingKB(false);
    }
  }, []);

  // Clear chat history
  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
    setSuggestions([]);
  }, []);

  // Toggle panel
  const togglePanel = useCallback(() => {
    setIsPanelOpen(prev => !prev);
  }, []);

  return (
    <NexoEstoqueContext
      value={{
        messages,
        isLoading,
        error,
        sendMessage,
        clearChat,
        queryKB,
        isQueryingKB,
        suggestions,
        setSuggestions,
        quickActions: DEFAULT_QUICK_ACTIONS,
        isPanelOpen,
        setIsPanelOpen,
        togglePanel,
      }}
    >
      {children}
    </NexoEstoqueContext>
  );
}

// =============================================================================
// Hook
// =============================================================================

export function useNexoEstoque() {
  const context = useContext(NexoEstoqueContext);
  if (context === undefined) {
    throw new Error('useNexoEstoque must be used within a NexoEstoqueProvider');
  }
  return context;
}
