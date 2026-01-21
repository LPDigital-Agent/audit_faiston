// =============================================================================
// Carrier AgentCore Service - Faiston NEXO Shipping Operations
// =============================================================================
// Purpose: Invoke AWS Bedrock AgentCore Runtime for Carrier/Shipping operations
// using JWT Bearer Token authentication.
//
// This service handles all shipping/logistics features:
// - Shipping quotes from carriers (VIPP API)
// - Postage creation and tracking
// - Postage status updates
// - Carrier recommendations
//
// ARCHITECTURE NOTE (2026-01-19):
// This service was separated from sgaAgentcore.ts as part of REFACTOR-001 Phase 2.
// Domain-Driven Design: Carrier/Shipping operations are now handled by a dedicated
// AgentCore runtime (faiston_carrier_orchestration) instead of being mixed with
// inventory operations.
//
// Configuration: See @/lib/config/agentcore.ts for ARN configuration
// =============================================================================

import { CARRIER_AGENTCORE_ARN } from '@/lib/config/agentcore';
import {
  createAgentCoreService,
  type AgentCoreRequest,
  type AgentCoreResponse,
  type InvokeOptions,
} from './agentcoreBase';
import type {
  SGAGetQuotesRequest,
  SGAGetQuotesResponse,
  SGARecommendCarrierRequest,
  SGARecommendCarrierResponse,
  SGACreatePostageRequest,
  SGACreatePostageResponse,
  SGAGetPostagesResponse,
  SGAUpdatePostageStatusResponse,
  SGATrackShipmentRequest,
  SGATrackShipmentResponse,
} from '@/lib/ativos/types';

// =============================================================================
// Storage Keys
// =============================================================================

const CARRIER_STORAGE_KEYS = {
  AGENTCORE_SESSION: 'faiston_carrier_agentcore_session',
} as const;

// =============================================================================
// Service Instance
// =============================================================================

const carrierService = createAgentCoreService({
  arn: CARRIER_AGENTCORE_ARN,
  sessionStorageKey: CARRIER_STORAGE_KEYS.AGENTCORE_SESSION,
  logPrefix: '[Carrier AgentCore]',
  sessionPrefix: 'carrier-session',
});

// =============================================================================
// Re-export Types
// =============================================================================

export type { AgentCoreRequest, AgentCoreResponse, InvokeOptions };

// =============================================================================
// AgentCore Response Parsing
// =============================================================================

/**
 * AgentCore HTTP response format - wraps agent output in content array.
 */
interface AgentCoreHttpResponse {
  role?: string;
  content?: Array<{ text?: string; type?: string }>;
}

/**
 * Orchestrator envelope structure - wraps specialist agent responses.
 * The orchestrator adds metadata (specialist_agent) and wraps the actual
 * response in a "response" field for tracing/debugging purposes.
 */
interface OrchestratorEnvelope<T> {
  success: boolean;
  specialist_agent?: string;
  response?: T;
  error?: string;
}

/**
 * Strip markdown code fences from a string before JSON parsing.
 * LLM responses often wrap JSON in markdown code blocks.
 */
function stripMarkdownCodeFences(text: string): string {
  const trimmed = text.trim();
  const match = trimmed.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/);
  if (match) {
    return match[1].trim();
  }
  return trimmed;
}

/**
 * Extracts and parses the actual response from AgentCore HTTP format.
 *
 * AgentCore returns responses in this nested structure:
 * 1. HTTP response: { role: "assistant", content: [{ text: "..." }] }
 * 2. Inner JSON string in text: { success, specialist_agent, response: {...} }
 * 3. Orchestrator envelope wraps the actual specialist response
 *
 * @param httpResponse - Raw response from AgentCore HTTP endpoint
 * @returns Extracted and parsed response data
 */
function extractResponse<T>(httpResponse: unknown): T {
  // Level 1: Extract text content from AgentCore HTTP format
  const agentCoreResponse = httpResponse as AgentCoreHttpResponse;
  const textContent = agentCoreResponse?.content?.find(
    (c) => c.type === 'text' || c.text
  );

  if (!textContent?.text) {
    console.warn('[Carrier AgentCore] No text content in response');
    return httpResponse as T;
  }

  // Level 2: Parse inner JSON string (may be wrapped in markdown)
  try {
    const cleanedText = stripMarkdownCodeFences(textContent.text);
    const innerJson = JSON.parse(cleanedText);

    // Level 3: Handle orchestrator envelope or direct response
    if (isOrchestratorEnvelope<T>(innerJson)) {
      if (!innerJson.success && innerJson.error) {
        console.error('[Carrier AgentCore] Orchestrator error:', innerJson.error);
        throw new Error(innerJson.error);
      }
      // If there's a nested 'response' field, unwrap it (A2A envelope)
      // Otherwise, return the response directly (direct tool call)
      if ('response' in innerJson && innerJson.response !== undefined) {
        return innerJson.response as T;
      }
      // Direct response - return as-is (already has success, carrier_id, etc.)
      return innerJson as unknown as T;
    }

    // Direct response without envelope
    return innerJson as T;
  } catch (parseError) {
    console.warn(
      '[Carrier AgentCore] Failed to parse inner JSON, returning raw text:',
      parseError
    );
    return { text: textContent.text } as T;
  }
}

/**
 * Type guard to check if response has orchestrator envelope structure.
 */
function isOrchestratorEnvelope<T>(obj: unknown): obj is OrchestratorEnvelope<T> {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'success' in obj &&
    typeof (obj as OrchestratorEnvelope<T>).success === 'boolean'
  );
}

// =============================================================================
// Main Invoke Function
// =============================================================================

/**
 * Invoke Carrier AgentCore with action-based request.
 *
 * Handles the full AgentCore response chain:
 * 1. AgentCore HTTP format: { role, content: [{ text }] }
 * 2. Orchestrator envelope: { specialist_agent, response }
 * 3. Returns the clean specialist response
 */
export async function invokeCarrierAgentCore<T = unknown>(
  request: AgentCoreRequest,
  options?: InvokeOptions | boolean
): Promise<AgentCoreResponse<T>> {
  const result = await carrierService.invoke<unknown>(request, options);
  return {
    data: extractResponse<T>(result.data),
    sessionId: result.sessionId,
  };
}

// =============================================================================
// Shipping Quote Operations (POSTING_ACTIONS)
// =============================================================================

/**
 * Get shipping quotes from multiple carriers.
 * Uses fresh session (useSession: false) since this is a stateless operation.
 */
export async function getShippingQuotes(
  params: SGAGetQuotesRequest
): Promise<AgentCoreResponse<SGAGetQuotesResponse>> {
  return invokeCarrierAgentCore<SGAGetQuotesResponse>(
    {
      action: 'get_shipping_quotes',
      ...params,
    },
    { useSession: false }
  );
}

/**
 * Get AI recommendation for best carrier.
 */
export async function recommendCarrier(
  params: SGARecommendCarrierRequest
): Promise<AgentCoreResponse<SGARecommendCarrierResponse>> {
  return invokeCarrierAgentCore<SGARecommendCarrierResponse>({
    action: 'recommend_carrier',
    ...params,
  });
}

// =============================================================================
// Postage Operations (POSTING_ACTIONS)
// =============================================================================

/**
 * Create a new postage/shipment order.
 * Stateless operation (useSession: false).
 *
 * This action triggers a composite flow in the carrier orchestrator:
 * 1. create_shipment -> Get tracking_code from VIPP
 * 2. save_posting -> Save to DynamoDB postings table
 * 3. Fallback lookup if needed
 *
 * @param params - Postage creation parameters including destination, weight, dimensions, and selected quote
 * @returns Created postage with tracking code and order details
 */
export async function createPostage(
  params: SGACreatePostageRequest
): Promise<AgentCoreResponse<SGACreatePostageResponse>> {
  return invokeCarrierAgentCore<SGACreatePostageResponse>(
    {
      action: 'create_postage',
      ...params,
    },
    { useSession: false }
  );
}

/**
 * Get all postages, optionally filtered by status.
 * Stateless operation (useSession: false).
 *
 * @param status - Optional status filter ('aguardando' | 'em_transito' | 'entregue' | 'cancelado')
 * @returns List of postages matching the filter
 */
export async function getPostages(
  status?: string
): Promise<AgentCoreResponse<SGAGetPostagesResponse>> {
  return invokeCarrierAgentCore<SGAGetPostagesResponse>(
    {
      action: 'get_postages',
      ...(status && { status }),
    },
    { useSession: false }
  );
}

/**
 * Update the status of a postage/shipment.
 * Stateless operation (useSession: false).
 *
 * @param posting_id - The ID of the postage to update
 * @param new_status - The new status ('aguardando' | 'em_transito' | 'entregue' | 'cancelado')
 * @returns Updated postage with new status
 */
export async function updatePostageStatus(
  posting_id: string,
  new_status: string
): Promise<AgentCoreResponse<SGAUpdatePostageStatusResponse>> {
  return invokeCarrierAgentCore<SGAUpdatePostageStatusResponse>(
    {
      action: 'update_postage_status',
      posting_id,
      new_status,
    },
    { useSession: false }
  );
}

// =============================================================================
// Tracking Operations
// =============================================================================

/**
 * Track a shipment by tracking code.
 *
 * @param params - Tracking request with tracking_code
 * @returns Tracking history and current status
 */
export async function trackShipment(
  params: SGATrackShipmentRequest
): Promise<AgentCoreResponse<SGATrackShipmentResponse>> {
  return invokeCarrierAgentCore<SGATrackShipmentResponse>({
    action: 'track_shipment',
    ...params,
  });
}

// =============================================================================
// Health Check
// =============================================================================

/**
 * Health check for carrier orchestrator.
 * Returns version info and agent status.
 */
export async function healthCheck(): Promise<
  AgentCoreResponse<{
    status: string;
    agent: string;
    version: string;
    timestamp: string;
  }>
> {
  return invokeCarrierAgentCore({
    action: 'health_check',
  });
}

// =============================================================================
// Carrier Admin Operations (Multi-Carrier Quote System)
// =============================================================================

/**
 * Response from listing carriers.
 */
export interface ListCarriersResponse {
  success: boolean;
  carriers: Array<{
    carrier_id: string;
    carrier_name: string;
    display_name?: string;
    is_active: boolean;
    current_version: number;
    total_routes?: number;
    last_upload_at?: string;
    last_upload_by?: string;
  }>;
  count?: number;
}

/**
 * Request for previewing carrier CSV.
 */
export interface PreviewCarrierCsvRequest {
  csv_content: string;
  carrier_name: string;
}

/**
 * Weight tier in carrier schema.
 */
export interface CarrierWeightTier {
  column_name: string;
  weight_kg: number;
}

/**
 * Response from CSV preview (schema detection).
 */
export interface PreviewCarrierCsvResponse {
  success: boolean;
  error?: string;
  schema: {
    carrier_name: string;
    carrier_id: string;
    region_column?: string;
    state_column?: string;
    zone_column?: string;
    delivery_days_column?: string;
    price_tiers: CarrierWeightTier[];
    excess_column?: string;
    price_format: string;
    detected_columns: string[];
    unmapped_columns: string[];
    detection_confidence: number;
    notes: string[];
  };
  validation: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  };
  sample_routes: Array<{
    uf: string;
    zone: string;
    [key: string]: string | number;
  }>;
  total_rows: number;
  headers: string[];
  detection_confidence: number;
}

/**
 * Request for ingesting carrier CSV.
 */
export interface IngestCarrierCsvRequest {
  csv_content: string;
  carrier_name: string;
  schema_override?: Record<string, unknown>;
}

/**
 * Response from CSV ingestion.
 */
export interface IngestCarrierCsvResponse {
  success: boolean;
  carrier_id: string;
  version: number;
  routes_created: number;
  message: string;
  errors?: Array<{ row?: number; error: string }>;
}

/**
 * List all registered carriers.
 *
 * Returns carrier metadata for admin UI including:
 * - Active/inactive status
 * - Current version
 * - Route count
 * - Last upload info
 *
 * @returns List of carrier info
 */
export async function listCarriers(): Promise<AgentCoreResponse<ListCarriersResponse>> {
  return invokeCarrierAgentCore<ListCarriersResponse>(
    {
      action: 'list_carriers',
    },
    { useSession: false }
  );
}

/**
 * Preview carrier CSV with LLM schema detection.
 *
 * Uses Gemini to analyze CSV structure and detect:
 * - Price columns by weight tier
 * - Region/state columns
 * - Zone (capital/interior)
 * - Delivery days
 * - Excess weight rate
 *
 * @param params.csv_content - Raw CSV content as string
 * @param params.carrier_name - Carrier name (e.g., "TRB")
 * @returns Schema preview with validation and sample routes
 */
export async function previewCarrierCsv(
  params: PreviewCarrierCsvRequest
): Promise<AgentCoreResponse<PreviewCarrierCsvResponse>> {
  // Backend expects base64-encoded CSV content
  const csvBase64 = btoa(unescape(encodeURIComponent(params.csv_content)));

  return invokeCarrierAgentCore<PreviewCarrierCsvResponse>(
    {
      action: 'preview_carrier_csv',
      csv_content_base64: csvBase64,
      carrier_name: params.carrier_name,
    },
    { useSession: false }
  );
}

/**
 * Ingest carrier CSV into DynamoDB.
 *
 * Parses CSV using detected (or overridden) schema and stores:
 * - Schema in CARRIER#{id}#SCHEMA#ACTIVE
 * - Routes in CARRIER#{id}#ROUTE#{uf}#{zone}
 * - Metadata in CARRIER#{id}#META#ACTIVE
 *
 * @param params.csv_content - Raw CSV content as string
 * @param params.carrier_name - Carrier name (e.g., "TRB")
 * @param params.schema_override - Optional pre-approved schema
 * @returns Ingestion result with routes created
 */
export async function ingestCarrierCsv(
  params: IngestCarrierCsvRequest
): Promise<AgentCoreResponse<IngestCarrierCsvResponse>> {
  // Backend expects base64-encoded CSV content
  const csvBase64 = btoa(unescape(encodeURIComponent(params.csv_content)));

  return invokeCarrierAgentCore<IngestCarrierCsvResponse>(
    {
      action: 'ingest_carrier_csv',
      csv_content_base64: csvBase64,
      carrier_name: params.carrier_name,
      ...(params.schema_override && { schema_override: params.schema_override }),
    },
    { useSession: false }
  );
}
