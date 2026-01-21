// =============================================================================
// Portal AgentCore Service - Faiston NEXO
// =============================================================================
// Purpose: Invoke AWS Bedrock AgentCore Runtime directly from the React SPA
// using JWT Bearer Token authentication.
//
// This service handles all AI features for the Faiston NEXO Portal:
// - NEXO AI Chat (central orchestrator)
// - Daily Summary (news, calendar mock, tips)
// - Tech News aggregation (RSS feeds)
// - A2A delegation to Academy and SGA agents
//
// Configuration: See @/lib/config/agentcore.ts for ARN configuration
// =============================================================================

import { PORTAL_AGENTCORE_ARN } from '@/lib/config/agentcore';
import {
  createAgentCoreService,
  type AgentCoreRequest,
  type AgentCoreResponse,
  type InvokeOptions,
} from './agentcoreBase';

// =============================================================================
// Session storage key
// =============================================================================

const PORTAL_SESSION_KEY = 'faiston_portal_agentcore_session';

// =============================================================================
// Service Instance
// =============================================================================

const portalService = createAgentCoreService({
  arn: PORTAL_AGENTCORE_ARN,
  sessionStorageKey: PORTAL_SESSION_KEY,
  logPrefix: '[Portal AgentCore]',
  sessionPrefix: 'portal-session',
});

// =============================================================================
// Re-export Types
// =============================================================================

export type { AgentCoreRequest, AgentCoreResponse, InvokeOptions };

// =============================================================================
// Types
// =============================================================================

// News types
export interface NewsArticle {
  id: string;
  title: string;
  source: string;
  sourceIcon: string;
  category: string;
  summary: string;
  url: string;
  publishedAt: string;
  readTime: number;
  author?: string;
  relevanceScore: number;
}

export interface NewsFeedResponse {
  success: boolean;
  articles: NewsArticle[];
  count: number;
  categories_fetched?: string[];
  errors?: Array<{ category: string; error: string }>;
  fetched_at?: string;
}

export interface NewsDigestResponse {
  success: boolean;
  digest: Record<string, {
    articles: NewsArticle[];
    count: number;
  }>;
  total_articles: number;
  categories: string[];
  generated_at: string;
}

// Chat types
export interface NexoChatRequest {
  question: string;
  conversation_history?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}

export interface NexoChatResponse {
  success: boolean;
  response: string;
  domain: 'portal' | 'academy' | 'inventory';
  delegated: boolean;
  fallback?: boolean;
  error_details?: string;
}

// Daily summary types - Discriminated unions for type safety
export interface NewsSectionData {
  total_articles: number;
  categories?: string[];
  articles?: NewsArticle[];
}

export interface CalendarSectionData {
  events_count?: number;
  next_event?: string;
}

export interface TeamsSectionData {
  unread_count?: number;
  channels?: string[];
}

export interface TipsSectionData {
  tip: string;
  category?: string;
}

export type DailySummarySectionData =
  | NewsSectionData
  | CalendarSectionData
  | TeamsSectionData
  | TipsSectionData;

export interface DailySummarySection {
  type: 'news' | 'calendar' | 'teams' | 'tips';
  title: string;
  data: DailySummarySectionData;
}

export interface DailySummaryResponse {
  success: boolean;
  summary: {
    greeting: string;
    date: string;
    sections: DailySummarySection[];
    generated_at: string;
  };
}

// =============================================================================
// Core Functions (delegated to base service)
// =============================================================================

export const invokePortalAgentCore = portalService.invoke;
export const getPortalSessionId = portalService.getSessionId;
export const clearPortalSession = portalService.clearSession;

// =============================================================================
// NEXO Chat Functions
// =============================================================================

/**
 * Send a chat message to NEXO Portal AI.
 * NEXO will handle the query directly or delegate to Academy/SGA agents.
 */
export async function nexoPortalChat(
  params: NexoChatRequest,
  signal?: AbortSignal
): Promise<AgentCoreResponse<NexoChatResponse>> {
  return invokePortalAgentCore<NexoChatResponse>(
    {
      action: 'nexo_chat',
      question: params.question,
      conversation_history: params.conversation_history,
    },
    { useSession: true, signal }
  );
}

// =============================================================================
// Daily Summary Functions
// =============================================================================

/**
 * Get personalized daily summary including news, calendar, and tips.
 */
export async function getDailySummary(
  includeNews: boolean = true,
  signal?: AbortSignal
): Promise<AgentCoreResponse<DailySummaryResponse>> {
  return invokePortalAgentCore<DailySummaryResponse>(
    {
      action: 'get_daily_summary',
      include_news: includeNews,
    },
    { useSession: true, signal }
  );
}

// =============================================================================
// News Functions
// =============================================================================

/**
 * Get aggregated tech news from RSS feeds.
 */
export async function getTechNews(
  params?: {
    categories?: string[];
    max_articles?: number;
    language?: 'all' | 'en' | 'pt-br';
  },
  signal?: AbortSignal
): Promise<AgentCoreResponse<NewsFeedResponse>> {
  return invokePortalAgentCore<NewsFeedResponse>(
    {
      action: 'get_tech_news',
      categories: params?.categories,
      max_articles: params?.max_articles || 20,
      language: params?.language || 'all',
    },
    { useSession: false, signal }
  );
}

/**
 * Get news for a specific category.
 */
export async function getNewsByCategory(
  category: string,
  maxArticles: number = 10,
  signal?: AbortSignal
): Promise<AgentCoreResponse<NewsFeedResponse>> {
  return invokePortalAgentCore<NewsFeedResponse>(
    {
      action: 'get_news_by_category',
      category,
      max_articles: maxArticles,
    },
    { useSession: false, signal }
  );
}

/**
 * Search news articles by keyword.
 */
export async function searchNews(
  query: string,
  params?: {
    categories?: string[];
    max_articles?: number;
  },
  signal?: AbortSignal
): Promise<AgentCoreResponse<NewsFeedResponse>> {
  return invokePortalAgentCore<NewsFeedResponse>(
    {
      action: 'search_news',
      query,
      categories: params?.categories,
      max_articles: params?.max_articles || 10,
    },
    { useSession: false, signal }
  );
}

/**
 * Get daily news digest with top articles per category.
 */
export async function getNewsDigest(
  signal?: AbortSignal
): Promise<AgentCoreResponse<NewsDigestResponse>> {
  return invokePortalAgentCore<NewsDigestResponse>(
    { action: 'get_news_digest' },
    { useSession: false, signal }
  );
}

// =============================================================================
// A2A Delegation Functions
// =============================================================================

/**
 * Delegate a question to Academy AgentCore.
 * Used when NEXO determines the query is learning-related.
 */
export async function delegateToAcademy(
  question: string,
  context?: Record<string, unknown>,
  signal?: AbortSignal
): Promise<AgentCoreResponse<unknown>> {
  return invokePortalAgentCore(
    {
      action: 'delegate_to_academy',
      question,
      context,
    },
    { useSession: true, signal }
  );
}

/**
 * Delegate a question to SGA Inventory AgentCore.
 * Used when NEXO determines the query is inventory-related.
 */
export async function delegateToSGA(
  question: string,
  context?: Record<string, unknown>,
  signal?: AbortSignal
): Promise<AgentCoreResponse<unknown>> {
  return invokePortalAgentCore(
    {
      action: 'delegate_to_sga',
      question,
      context,
    },
    { useSession: true, signal }
  );
}

// =============================================================================
// Health Check
// =============================================================================

/**
 * Check Portal AgentCore health status.
 */
export async function checkPortalHealth(
  signal?: AbortSignal
): Promise<AgentCoreResponse<{
  status: string;
  module: string;
  version: string;
  timestamp: string;
  capabilities: string[];
}>> {
  return invokePortalAgentCore(
    { action: 'health_check' },
    { useSession: false, signal }
  );
}
