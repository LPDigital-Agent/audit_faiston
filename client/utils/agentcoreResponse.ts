// =============================================================================
// AgentCore A2A Response Extraction Utility - Faiston NEXO
// =============================================================================
// Purpose: Extract actual response data from Strands A2A wrapped responses.
//
// Strands A2A wraps specialist agent responses with observability metadata:
// {
//   success: boolean,
//   specialist_agent: string,   // Agent that handled the request
//   response: T,                // Actual payload from specialist
//   request_id: string,         // Request tracing ID
//   debug_analysis?: DebugAnalysis  // CRITICAL-001: Error enrichment from Debug Agent
// }
//
// This utility extracts the inner response for frontend consumption while
// preserving the Agentic architecture pattern on the backend.
// =============================================================================

/**
 * Strands A2A wrapped response format.
 * All specialist agent responses include observability metadata.
 */
export interface AgentWrappedResponse<T> {
  success: boolean;
  specialist_agent: string;
  response: T;
  request_id: string;
  debug_analysis?: DebugAnalysis; // CRITICAL-001: Error enrichment from Debug Agent
}

// =============================================================================
// CRITICAL-001 FIX: Debug Agent Analysis Types
// =============================================================================
// These types represent the enriched error analysis returned by Debug Agent.
// The Debug Agent analyzes errors, searches documentation, and queries memory
// patterns to provide actionable debugging information.
// =============================================================================

/**
 * Root cause analysis with confidence level.
 */
export interface DebugRootCause {
  /** Description of the potential cause */
  cause: string;
  /** Confidence level (0.0 - 1.0) */
  confidence: number;
  /** Evidence supporting this cause */
  evidence: string[];
  /** Source of the analysis (memory_pattern, documentation, inference) */
  source: 'memory_pattern' | 'documentation' | 'inference';
}

/**
 * Documentation link with relevance context.
 */
export interface DebugDocumentationLink {
  /** Document title */
  title: string;
  /** Full URL to documentation */
  url: string;
  /** Why this document is relevant */
  relevance: string;
}

/**
 * Similar error pattern from memory.
 */
export interface DebugSimilarPattern {
  /** Pattern identifier */
  pattern_id: string;
  /** Similarity score (0.0 - 1.0) */
  similarity: number;
  /** How this pattern was resolved */
  resolution: string;
}

/**
 * Debug Agent analysis result attached to error responses.
 *
 * This structure contains enriched error information including:
 * - Technical explanation in pt-BR
 * - Root cause analysis with confidence levels
 * - Step-by-step debugging instructions
 * - Relevant documentation links
 * - Similar patterns from memory
 */
export interface DebugAnalysis {
  /** Unique error signature for deduplication and pattern matching */
  error_signature: string;
  /** Original error type (e.g., ValidationError, TimeoutError) */
  error_type: string;
  /** Technical explanation of the error (pt-BR) */
  technical_explanation: string;
  /** Root cause analysis with confidence levels */
  root_causes: DebugRootCause[];
  /** Step-by-step debugging instructions */
  debugging_steps: string[];
  /** Relevant documentation links */
  documentation_links: DebugDocumentationLink[];
  /** Similar error patterns from memory */
  similar_patterns: DebugSimilarPattern[];
  /** Whether the error is recoverable (retry may succeed) */
  recoverable: boolean;
  /** Suggested action for the user */
  suggested_action: 'retry' | 'fallback' | 'escalate' | 'abort';
  /** BUG-027: Whether AI (Gemini) was used for analysis (false = rule-based fallback) */
  llm_powered: boolean;
}

/**
 * Type guard to check if response has A2A agent metadata.
 */
export function isAgentWrappedResponse<T>(data: unknown): data is AgentWrappedResponse<T> {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return 'specialist_agent' in obj && 'response' in obj;
}

/**
 * Response with optional debug analysis attached.
 * HIGH-002 FIX: Preserves debug_analysis when extracting from wrapped responses.
 */
export type ResponseWithDebugAnalysis<T> = T & {
  debug_analysis?: DebugAnalysis;
};

/**
 * Extract actual response data from AgentCore A2A wrapped responses.
 *
 * Handles both wrapped A2A responses and direct/legacy flat responses
 * for backward compatibility during migration.
 *
 * HIGH-002 FIX: Now preserves debug_analysis from the wrapper level,
 * attaching it to the returned response for downstream access.
 *
 * @param data - The response data (potentially wrapped)
 * @returns The inner response payload (type T) with optional debug_analysis
 *
 * @example
 * ```typescript
 * // Wrapped A2A response with debug analysis
 * const wrapped = {
 *   success: true,
 *   specialist_agent: "intake",
 *   response: { upload_url: "https://...", s3_key: "uploads/..." },
 *   request_id: "direct-get_nf_upload_url",
 *   debug_analysis: { error_type: "ValidationError", ... }
 * };
 * const data = extractAgentResponse<UploadUrlResponse>(wrapped);
 * // data = { upload_url: "https://...", s3_key: "uploads/...", debug_analysis: {...} }
 *
 * // Direct/legacy response (unchanged)
 * const flat = { upload_url: "https://...", s3_key: "uploads/..." };
 * const data2 = extractAgentResponse<UploadUrlResponse>(flat);
 * // data2 = { upload_url: "https://...", s3_key: "uploads/..." }
 * ```
 */
export function extractAgentResponse<T>(data: unknown): ResponseWithDebugAnalysis<T> {
  if (!data || typeof data !== 'object') {
    return data as ResponseWithDebugAnalysis<T>;
  }

  // Check if this is a wrapped A2A response
  if (isAgentWrappedResponse<T>(data)) {
    // HIGH-002 FIX: Preserve debug_analysis from wrapper level
    const response = data.response as ResponseWithDebugAnalysis<T>;

    // Attach debug_analysis to the response if present at wrapper level
    if (data.debug_analysis) {
      response.debug_analysis = data.debug_analysis;
    }

    return response;
  }

  // Already flat (legacy or direct response)
  return data as ResponseWithDebugAnalysis<T>;
}

/**
 * Extract agent metadata from a wrapped response.
 * Returns null if the response is not wrapped.
 */
export function extractAgentMetadata(data: unknown): {
  specialist_agent: string;
  request_id: string;
} | null {
  if (!isAgentWrappedResponse(data)) return null;
  return {
    specialist_agent: data.specialist_agent,
    request_id: data.request_id,
  };
}

// =============================================================================
// CRITICAL-001 FIX: Debug Analysis Extraction
// =============================================================================

/**
 * Extract debug analysis from a response if present.
 *
 * CRITICAL-001 FIX: This function extracts the Debug Agent's enriched
 * error analysis from responses. It checks multiple locations where
 * debug_analysis might be attached:
 * 1. Wrapper level (AgentWrappedResponse.debug_analysis)
 * 2. Inner response level (response.debug_analysis)
 * 3. Direct object level (for flat responses)
 *
 * @param data - The response data to extract debug analysis from
 * @returns DebugAnalysis if present, null otherwise
 *
 * @example
 * ```typescript
 * const response = await api.importFile(file);
 * const debug = extractDebugAnalysis(response);
 * if (debug) {
 *   console.log('Root causes:', debug.root_causes);
 *   console.log('Steps:', debug.debugging_steps);
 * }
 * ```
 */
export function extractDebugAnalysis(data: unknown): DebugAnalysis | null {
  if (!data || typeof data !== 'object') return null;

  const obj = data as Record<string, unknown>;

  // Check wrapper level first (AgentWrappedResponse)
  if ('debug_analysis' in obj && obj.debug_analysis) {
    return obj.debug_analysis as DebugAnalysis;
  }

  // Check inner response level (nested in response field)
  if ('response' in obj && obj.response && typeof obj.response === 'object') {
    const inner = obj.response as Record<string, unknown>;
    if ('debug_analysis' in inner && inner.debug_analysis) {
      return inner.debug_analysis as DebugAnalysis;
    }
  }

  return null;
}

/**
 * Check if debug analysis is present in a response.
 *
 * @param data - The response data to check
 * @returns True if debug analysis is present
 */
export function hasDebugAnalysis(data: unknown): boolean {
  return extractDebugAnalysis(data) !== null;
}

// =============================================================================
// BUG-022 FIX: Safe Error Message Extraction
// =============================================================================
// Handles double-encoded JSON strings that can occur when A2A transport
// serializes already-JSON responses (e.g., '"success"' instead of 'success')
// =============================================================================

/**
 * Safely extract error message from potentially double-encoded string.
 *
 * BUG-022 FIX: Now RECURSIVE to handle multiple levels of JSON encoding.
 * This can happen when A2A transport serializes already-JSON responses
 * multiple times (e.g., '"\\"success\\""' → '"success"' → 'success').
 *
 * Handles cases where backend sends:
 * - "\"success\"" (double-encoded string)
 * - "\"\\\"nested\\\"\"" (triple-encoded string)
 * - "success" (normal string)
 * - { error: "message" } (object with error field)
 *
 * @param value - The value to extract error message from
 * @param maxDepth - Maximum recursion depth to prevent infinite loops (default: 5)
 * @returns The unwrapped error message string
 *
 * @example
 * ```typescript
 * safeExtractErrorMessage('"success"'); // Returns: 'success'
 * safeExtractErrorMessage('"\\"nested\\""'); // Returns: 'nested'
 * safeExtractErrorMessage('normal error'); // Returns: 'normal error'
 * safeExtractErrorMessage({ error: '"nested"' }); // Returns: 'nested'
 * ```
 */
export function safeExtractErrorMessage(value: unknown, maxDepth = 5): string {
  // Guard against infinite recursion
  if (maxDepth <= 0) {
    return typeof value === 'string' ? value : 'Erro desconhecido';
  }

  if (typeof value === 'string') {
    // Try to unwrap if it looks like a JSON-encoded string
    if (value.startsWith('"') && value.endsWith('"')) {
      try {
        const parsed = JSON.parse(value);
        if (typeof parsed === 'string') {
          // RECURSIVE: Continue unwrapping until we get a non-encoded string
          return safeExtractErrorMessage(parsed, maxDepth - 1);
        }
      } catch {
        // Return as-is if parsing fails
      }
    }

    // BUG-022 v10 FIX: Detect "success" as error (semantic mismatch)
    // When double-encoding unwraps to the literal word "success", it's meaningless
    // Check ALL quote variations + trim for robustness
    const trimmedValue = typeof value === 'string' ? value.trim() : '';
    if (trimmedValue === 'success' || trimmedValue === '"success"' || trimmedValue === "'success'") {
      console.warn('[BUG-022 v10] Detected "success" as error value - semantic mismatch:', value);
      return 'Erro interno: resposta malformada do servidor';
    }

    return value;
  }

  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    if ('error' in obj) {
      return safeExtractErrorMessage(obj.error, maxDepth - 1);
    }
    if ('message' in obj) {
      return safeExtractErrorMessage(obj.message, maxDepth - 1);
    }
  }

  return 'Erro desconhecido';
}

/**
 * Check if a response indicates an error.
 *
 * @param data - The response data to check
 * @returns True if the response contains error indicators
 */
export function isErrorResponse(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const obj = data as Record<string, unknown>;
  return obj.success === false || 'error' in obj;
}
