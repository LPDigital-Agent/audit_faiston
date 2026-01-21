// =============================================================================
// useNexoAI Hook - Faiston Academy
// =============================================================================
// Hook for NEXO AI Chat (renamed from Sasha).
// Provides conversation management with the AI tutor.
// =============================================================================

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { nexoChat } from '@/services/academyAgentcore';
import type { NexoChatResponse } from '@/lib/academy/types';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface UseNexoAIOptions {
  courseId: string;
  episodeId: string;
  episodeTitle?: string;
  transcription: string;
}

const getStorageKey = (courseId: string, episodeId: string) =>
  `faiston_academy_nexo_chat_${courseId}_${episodeId}`;

export function useNexoAI({
  courseId,
  episodeId,
  episodeTitle = 'Aula',
  transcription,
}: UseNexoAIOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        setMessages(
          parsed.map((msg: ChatMessage) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          }))
        );
      }
    } catch (e) {
      console.error('Failed to load chat history:', e);
    }
  }, [courseId, episodeId]);

  // Save to localStorage when messages change
  useEffect(() => {
    if (messages.length > 0) {
      const storageKey = getStorageKey(courseId, episodeId);
      try {
        localStorage.setItem(storageKey, JSON.stringify(messages));
      } catch (e) {
        console.error('Failed to save chat history:', e);
      }
    }
  }, [messages, courseId, episodeId]);

  // Chat mutation
  const chatMutation = useMutation({
    mutationFn: async (question: string): Promise<NexoChatResponse> => {
      const conversationHistory = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const { data } = await nexoChat({
        question,
        transcription,
        episode_title: episodeTitle,
        conversation_history: conversationHistory,
      });

      return data;
    },
    onMutate: () => {
      setIsTyping(true);
    },
    onSuccess: (data, question) => {
      // Add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: question,
        timestamp: new Date(),
      };

      // Add assistant message
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.answer,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsTyping(false);
    },
    onError: () => {
      setIsTyping(false);
    },
  });

  // Send message
  const sendMessage = useCallback(
    (question: string) => {
      if (!question.trim()) return;
      chatMutation.mutate(question);
    },
    [chatMutation]
  );

  // Clear chat history
  const clearChat = useCallback(() => {
    setMessages([]);
    const storageKey = getStorageKey(courseId, episodeId);
    try {
      localStorage.removeItem(storageKey);
    } catch (e) {
      console.error('Failed to clear chat history:', e);
    }
  }, [courseId, episodeId]);

  return {
    messages,
    isTyping,
    sendMessage,
    clearChat,
    isLoading: chatMutation.isPending,
    error: chatMutation.error,
    hasMessages: messages.length > 0,
  };
}

// Type alias for backwards compatibility
export type ConversationMessage = ChatMessage;

// =============================================================================
// Standalone Chat Mutation (for custom message management)
// =============================================================================

interface NexoChatRequest {
  question: string;
  transcription: string;
  episodeTitle?: string;
  conversationHistory?: Array<{ role: string; parts: { text: string }[] }>;
}

/**
 * Raw mutation hook for NEXO AI chat.
 * Use this when you want to manage messages yourself.
 */
export function useNexoAIChatMutation() {
  return useMutation({
    mutationFn: async (request: NexoChatRequest): Promise<NexoChatResponse> => {
      // Convert Gemini-style history to simple format for API
      const conversationHistory = request.conversationHistory?.map((msg) => ({
        role: msg.role === 'model' ? 'assistant' : msg.role,
        content: msg.parts[0]?.text || '',
      }));

      const { data } = await nexoChat({
        question: request.question,
        transcription: request.transcription,
        episode_title: request.episodeTitle,
        conversation_history: conversationHistory,
      });

      return data;
    },
  });
}
