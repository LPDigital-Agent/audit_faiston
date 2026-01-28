// =============================================================================
// AgentCore Base Service - Faiston NEXO
// =============================================================================
// Purpose: Unified base for all AgentCore service invocations.
// This eliminates ~450 lines of duplicated code across Academy, SGA, and Portal.
//
// Pattern: Factory function that creates configured invoke functions.
// Each service (Academy, SGA, Portal) uses this base with its own config.
//
// Features:
// - Retry logic with exponential backoff (502, 503, 504)
// - Session management (browser sessionStorage)
// - JWT Bearer token authentication
// - SSE (Server-Sent Events) response parsing
// - Proper error handling with user-friendly messages
// =============================================================================

import { ensureValidAccessToken } from '@/utils/tokenRefresh';
import { AGENTCORE_ENDPOINT } from '@/lib/config/agentcore';
import { safeExtractErrorMessage, type DebugAnalysis } from '@/utils/agentcoreResponse';

// =============================================================================
// BUG-027 FIX: Custom Error Class with Debug Analysis
// =============================================================================
// Preserves debug_analysis from backend errors for DebugAnalysisPanel display.
// Standard Error loses all metadata - this class preserves it.
// =============================================================================

export class AgentCoreError extends Error {
  public readonly debug_analysis?: DebugAnalysis;
  public readonly status?: number;
  public readonly originalResponse?: unknown;

  constructor(
    message: string,
    options?: {
      debug_analysis?: DebugAnalysis;
      status?: number;
      originalResponse?: unknown;
    }
  ) {
    super(message);
    this.name = 'AgentCoreError';
    this.debug_analysis = options?.debug_analysis;
    this.status = options?.status;
    this.originalResponse = options?.originalResponse;
  }
}

// =============================================================================
// Types
// =============================================================================

export interface AgentCoreRequest {
  action: string;
  [key: string]: unknown;
}

// AUDIT-002: DebugAnalysis type is imported from @/utils/agentcoreResponse

export interface AgentCoreResponse<T = unknown> {
  data: T;
  sessionId: string;
  /** AUDIT-002: Debug analysis from DebugHook error enrichment */
  debug_analysis?: DebugAnalysis;
}

export interface InvokeOptions {
  useSession?: boolean;
  signal?: AbortSignal;
}

export interface AgentCoreServiceConfig {
  /** ARN of the AgentCore runtime */
  arn: string;
  /** Key for storing session ID in sessionStorage */
  sessionStorageKey: string;
  /** Prefix for log messages (e.g., "[Academy AgentCore]") */
  logPrefix: string;
  /** Optional prefix for session IDs (default: "session") */
  sessionPrefix?: string;
}

// =============================================================================
// Retry Configuration
// =============================================================================

const RETRY_CONFIG = {
  maxRetries: 3,
  initialDelayMs: 3000,
  retryableStatuses: [502, 503, 504],
};

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// =============================================================================
// Session Management Factory
// =============================================================================

function createSessionManager(config: AgentCoreServiceConfig) {
  const prefix = config.sessionPrefix || 'session';

  function generateSessionId(): string {
    return `${prefix}-${crypto.randomUUID().replace(/-/g, '')}`;
  }

  function getSessionId(): string {
    if (typeof window === 'undefined') return generateSessionId();

    try {
      let sessionId = sessionStorage.getItem(config.sessionStorageKey);
      if (!sessionId) {
        sessionId = generateSessionId();
        sessionStorage.setItem(config.sessionStorageKey, sessionId);
      }
      return sessionId;
    } catch {
      return generateSessionId();
    }
  }

  function clearSession(): void {
    if (typeof window === 'undefined') return;

    try {
      sessionStorage.removeItem(config.sessionStorageKey);
    } catch {
      // sessionStorage not available
    }
  }

  return { generateSessionId, getSessionId, clearSession };
}

// =============================================================================
// SSE Response Parser
// =============================================================================

async function parseSSEResponse<T>(response: Response): Promise<T> {
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body for streaming');
  }

  const decoder = new TextDecoder();
  const chunks: string[] = [];

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data && data !== '[DONE]') {
          chunks.push(data);
        }
      }
    }
  }

  const fullResponse = chunks.join('');
  try {
    return JSON.parse(fullResponse) as T;
  } catch {
    return fullResponse as unknown as T;
  }
}

// =============================================================================
// AgentCore Service Factory
// =============================================================================

/**
 * Creates a configured AgentCore service with invoke, session management,
 * and config helpers.
 *
 * @example
 * ```typescript
 * const academyService = createAgentCoreService({
 *   arn: ACADEMY_AGENTCORE_ARN,
 *   sessionStorageKey: 'faiston_academy_session',
 *   logPrefix: '[Academy AgentCore]',
 * });
 *
 * const response = await academyService.invoke<MyResponse>({
 *   action: 'my_action',
 *   param: 'value',
 * });
 * ```
 */
export function createAgentCoreService(config: AgentCoreServiceConfig) {
  const sessionManager = createSessionManager(config);

  async function invoke<T = unknown>(
    request: AgentCoreRequest,
    options: InvokeOptions | boolean = true
  ): Promise<AgentCoreResponse<T>> {
    const opts: InvokeOptions = typeof options === 'boolean'
      ? { useSession: options }
      : options;
    const { useSession = true, signal } = opts;

    // Get JWT token - ensures token is valid and refreshes if expiring soon
    const token = await ensureValidAccessToken();
    if (!token) {
      throw new Error('Nao autenticado. Por favor, faca login novamente.');
    }

    // Build URL
    const encodedArn = encodeURIComponent(config.arn);
    const url = `${AGENTCORE_ENDPOINT}/runtimes/${encodedArn}/invocations?qualifier=DEFAULT`;

    // Get session ID
    const sessionId = useSession
      ? sessionManager.getSessionId()
      : sessionManager.generateSessionId();

    // Retry loop
    let lastError: Error | null = null;
    for (let attempt = 0; attempt <= RETRY_CONFIG.maxRetries; attempt++) {
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
            'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId,
          },
          body: JSON.stringify(request),
          signal,
        });

        if (!response.ok) {
          const errorBody = await response.text();
          let errorMessage = `AgentCore error: ${response.status} ${response.statusText}`;
          let debugAnalysis: DebugAnalysis | undefined;
          let originalResponse: unknown;

          try {
            const errorJson = JSON.parse(errorBody);
            originalResponse = errorJson;

            // BUG-027 FIX: Extract debug_analysis if present
            if (errorJson.debug_analysis && typeof errorJson.debug_analysis === 'object') {
              debugAnalysis = errorJson.debug_analysis as DebugAnalysis;
              console.log('[AgentCoreBase] BUG-027: Extracted debug_analysis from error response');
            }

            // BUG-022 FIX: Use safeExtractErrorMessage to handle double-encoded errors
            const rawMessage = errorJson.message || errorJson.Message || errorJson.error;
            errorMessage = rawMessage ? safeExtractErrorMessage(rawMessage) : errorMessage;
          } catch {
            if (errorBody) {
              // BUG-022 FIX: Even raw error body might be double-encoded
              errorMessage = safeExtractErrorMessage(errorBody);
            }
          }

          if (response.status === 401) {
            throw new AgentCoreError('Sessao expirada. Por favor, faca login novamente.', {
              status: 401,
              debug_analysis: debugAnalysis,
            });
          }
          if (response.status === 403) {
            throw new AgentCoreError('Acesso negado. Verifique suas permissoes.', {
              status: 403,
              debug_analysis: debugAnalysis,
            });
          }

          if (RETRY_CONFIG.retryableStatuses.includes(response.status) && attempt < RETRY_CONFIG.maxRetries) {
            const delayMs = RETRY_CONFIG.initialDelayMs * Math.pow(2, attempt);
            console.warn(`${config.logPrefix} Received ${response.status}, retrying in ${delayMs}ms...`);
            lastError = new AgentCoreError(errorMessage, {
              status: response.status,
              debug_analysis: debugAnalysis,
              originalResponse,
            });
            await sleep(delayMs);
            continue;
          }

          // BUG-027 FIX: Throw AgentCoreError with debug_analysis preserved
          throw new AgentCoreError(errorMessage, {
            status: response.status,
            debug_analysis: debugAnalysis,
            originalResponse,
          });
        }

        // Parse response
        const contentType = response.headers.get('content-type') || '';

        if (contentType.includes('text/event-stream')) {
          const data = await parseSSEResponse<T>(response);
          return { data, sessionId };
        }

        if (contentType.includes('application/json')) {
          const data = (await response.json()) as T;
          return { data, sessionId };
        }

        const text = await response.text();
        try {
          const data = JSON.parse(text) as T;
          return { data, sessionId };
        } catch {
          return { data: text as unknown as T, sessionId };
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          throw error;
        }
        lastError = error instanceof Error ? error : new Error(String(error));
        if (attempt < RETRY_CONFIG.maxRetries) {
          const delayMs = RETRY_CONFIG.initialDelayMs * Math.pow(2, attempt);
          console.warn(`${config.logPrefix} Error, retrying in ${delayMs}ms...`, error);
          await sleep(delayMs);
          continue;
        }
      }
    }

    throw lastError || new Error('AgentCore request failed after all retries');
  }

  function getConfig() {
    return {
      endpoint: AGENTCORE_ENDPOINT,
      arn: config.arn,
      configured: Boolean(config.arn),
    };
  }

  return {
    invoke,
    getSessionId: sessionManager.getSessionId,
    clearSession: sessionManager.clearSession,
    getConfig,
  };
}

// Note: AgentCoreServiceConfig is already exported at definition
