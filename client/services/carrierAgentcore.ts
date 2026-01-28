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
  // Reversa (Reverse Logistics) types
  SGACreateReversaRequest,
  SGACreateReversaResponse,
  SGAGetReversasResponse,
  SGAUpdateReversaStatusResponse,
  SGACancelReversaResponse,
  SGASendReversaWhatsAppResponse,
  SGATrackReversaResponse,
  SGAReversaStatus,
  // Tiflux Integration types
  GetTifluxTicketsResponse,
  GetTifluxTicketDetailResponse,
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
 * AgentCore content item - can have multiple formats:
 * - Format 1: { text: "JSON" } - standard text response
 * - Format 2: { type: "tool_result", content: "JSON" } - tool result format
 *
 * BUG-039v2: Extended to handle all observed AgentCore response formats.
 */
interface AgentCoreContentItem {
  text?: string; // Format 1: Standard text response
  type?: string; // e.g., "text", "tool_result"
  content?: string; // Format 2: Tool result content
}

/**
 * AgentCore HTTP response format - wraps agent output in content array.
 */
interface AgentCoreHttpResponse {
  role?: string;
  content?: AgentCoreContentItem[];
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
 * Convert Python dict syntax to valid JSON.
 * AgentCore sometimes returns Python repr instead of JSON:
 * - Single quotes -> double quotes
 * - True/False/None -> true/false/null
 * - Decimal('123.45') -> 123.45
 */
function pythonDictToJson(text: string): string {
  let result = text;

  // Replace Decimal('xxx') with just the number
  result = result.replace(/Decimal\('([^']+)'\)/g, '$1');

  // Replace Python booleans and None with JSON equivalents
  // Use word boundaries to avoid replacing inside strings
  result = result.replace(/\bTrue\b/g, 'true');
  result = result.replace(/\bFalse\b/g, 'false');
  result = result.replace(/\bNone\b/g, 'null');

  // Replace single quotes with double quotes
  // This is a simplified approach - handles most cases
  result = result.replace(/'/g, '"');

  return result;
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
  // Check if response is a string (Python dict or JSON string)
  if (typeof httpResponse === 'string') {
    try {
      // Try JSON first, then Python dict syntax
      try {
        return JSON.parse(httpResponse) as T;
      } catch {
        const jsonText = pythonDictToJson(httpResponse);
        return JSON.parse(jsonText) as T;
      }
    } catch (e) {
      console.warn('[Carrier AgentCore] Failed to parse string response:', e);
      return { text: httpResponse } as T;
    }
  }

  // Check if response is already a direct tool result (bypasses LLM)
  // Direct tool results have 'success' property but no 'content' array
  const directResponse = httpResponse as Record<string, unknown>;
  if (
    typeof directResponse === 'object' &&
    directResponse !== null &&
    'success' in directResponse &&
    !('content' in directResponse)
  ) {
    // Direct tool call response - return as-is
    return httpResponse as T;
  }

  // Level 1: Extract JSON payload from AgentCore HTTP format
  // BUG-039v2: Handle multiple content formats from AgentCore
  const agentCoreResponse = httpResponse as AgentCoreHttpResponse;
  const firstContent = agentCoreResponse?.content?.[0];

  // BUG-039v2: Extract JSON payload from various content formats
  let jsonPayload: string | undefined;

  if (firstContent) {
    // Format 1: { text: "JSON" } - standard text response (most common)
    if ('text' in firstContent && typeof firstContent.text === 'string') {
      jsonPayload = firstContent.text;
    }
    // Format 2: { type: "tool_result", content: "JSON" } - tool result format
    else if (
      'type' in firstContent &&
      firstContent.type === 'tool_result' &&
      typeof firstContent.content === 'string'
    ) {
      jsonPayload = firstContent.content;
    }
    // Format 3: { content: "JSON" } - direct content field (fallback)
    else if ('content' in firstContent && typeof firstContent.content === 'string') {
      jsonPayload = firstContent.content;
    }
  }

  if (!jsonPayload) {
    console.warn(
      '[Carrier AgentCore] BUG-039v2: Could not extract JSON from response:',
      firstContent ? JSON.stringify(firstContent).slice(0, 200) : 'no content'
    );
    return httpResponse as T;
  }

  // Level 2: Parse inner JSON string (may be wrapped in markdown or Python syntax)
  try {
    const cleanedText = stripMarkdownCodeFences(jsonPayload);

    // Try parsing as JSON first, then as Python dict syntax
    let innerJson: unknown;
    try {
      innerJson = JSON.parse(cleanedText);
    } catch {
      // If JSON parse fails, try converting from Python dict syntax
      const jsonText = pythonDictToJson(cleanedText);
      innerJson = JSON.parse(jsonText);
    }

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
      '[Carrier AgentCore] BUG-039v2: Failed to parse inner JSON, returning raw text:',
      parseError,
      jsonPayload.slice(0, 200)
    );
    return { text: jsonPayload } as T;
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
 * V2 column mapping from agent schema detection.
 */
export interface CarrierColumnMapping {
  column_name: string;
  role: string;
  data_type: string;
  metadata: Record<string, unknown>;
}

/**
 * V2 carrier schema produced by the agent.
 */
export interface CarrierSchemaV2 {
  carrier_name: string;
  carrier_id: string;
  schema_version: string;
  columns: CarrierColumnMapping[];
  route_key_roles: string[];
  pricing_model: { type: string; params: Record<string, unknown> };
  resolution_strategy: { type: string; params: Record<string, unknown> };
  price_format: string;
  notes?: string[];
}

/**
 * Response from CSV preview (V2 schema detection).
 */
export interface PreviewCarrierCsvResponse {
  success: boolean;
  error?: string;
  parsed_data?: { headers: string[]; rows: Record<string, string>[]; sample_values: Record<string, string[]> };
  v2_schema?: CarrierSchemaV2;
  heuristic_hint?: { schema: Record<string, unknown>; confidence: number };
  validation?: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  };
  total_rows: number;
  headers: string[];
  needs_llm_schema_detection?: boolean;
}

/**
 * Request for ingesting carrier CSV.
 * schema_override is REQUIRED — the agent produces it during preview.
 */
export interface IngestCarrierCsvRequest {
  csv_content: string;
  carrier_name: string;
  schema_override: CarrierSchemaV2;
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
 * Delete a carrier and all its data from DynamoDB.
 */
export interface DeleteCarrierResponse {
  success: boolean;
  carrier_id: string;
  items_deleted: number;
  message: string;
  error?: string;
}

export async function deleteCarrier(
  carrierId: string
): Promise<AgentCoreResponse<DeleteCarrierResponse>> {
  return invokeCarrierAgentCore<DeleteCarrierResponse>(
    {
      action: 'delete_carrier',
      carrier_id: carrierId,
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
      schema_override: params.schema_override,
    },
    { useSession: false }
  );
}

// =============================================================================
// Reversa (Reverse Logistics) Functions
// =============================================================================

/**
 * Create a new reversa (reverse logistics request).
 * Generates an e-ticket via VIPP API and saves the reversa record.
 *
 * @param request - Reversa creation parameters
 * @returns Created reversa with authorization code (e-ticket)
 */
export async function createReversa(
  request: SGACreateReversaRequest
): Promise<AgentCoreResponse<SGACreateReversaResponse>> {
  return invokeCarrierAgentCore<SGACreateReversaResponse>(
    {
      action: 'create_reversa',
      origin: request.origin,
      equipment: request.equipment,
      service_code: request.service_code || '3301', // Default to PAC REVERSA
      declared_value: request.declared_value || 0,
      technician_id: request.technician_id,
      technician_name: request.technician_name,
      ticket_id: request.ticket_id,
      project_id: request.project_id,
      destination_depot: request.destination_depot || 'SP-MATRIZ',
      notes: request.notes,
    },
    { useSession: false }
  );
}

/**
 * Get reversas with optional filters.
 *
 * @param status - Optional status filter (pendente, postado, em_transito, etc.)
 * @param technician_id - Optional technician filter
 * @param limit - Maximum number of results (default: 50)
 * @returns List of reversas matching filters
 */
export async function getReversas(
  status?: SGAReversaStatus,
  technician_id?: string,
  limit: number = 50
): Promise<AgentCoreResponse<SGAGetReversasResponse>> {
  return invokeCarrierAgentCore<SGAGetReversasResponse>(
    {
      action: 'get_reversas',
      ...(status && { status }),
      ...(technician_id && { technician_id }),
      limit,
    },
    { useSession: false }
  );
}

/**
 * Update the status of a reversa.
 *
 * @param reversa_id - Reversa ID to update
 * @param new_status - New status value
 * @param tracking_code - Optional tracking code (when status changes to 'postado')
 * @param notes - Optional notes about the status change
 * @returns Updated reversa
 */
export async function updateReversaStatus(
  reversa_id: string,
  new_status: SGAReversaStatus,
  tracking_code?: string,
  notes?: string
): Promise<AgentCoreResponse<SGAUpdateReversaStatusResponse>> {
  return invokeCarrierAgentCore<SGAUpdateReversaStatusResponse>(
    {
      action: 'update_reversa_status',
      reversa_id,
      new_status,
      ...(tracking_code && { tracking_code }),
      ...(notes && { notes }),
    },
    { useSession: false }
  );
}

/**
 * Cancel a reversa (only works for 'pendente' status).
 *
 * @param reversa_id - Reversa ID to cancel
 * @param reason - Cancellation reason
 * @returns Cancelled reversa
 */
export async function cancelReversa(
  reversa_id: string,
  reason: string = 'Cancelled by user'
): Promise<AgentCoreResponse<SGACancelReversaResponse>> {
  return invokeCarrierAgentCore<SGACancelReversaResponse>(
    {
      action: 'cancel_reversa',
      reversa_id,
      reason,
    },
    { useSession: false }
  );
}

/**
 * Track a reversa shipment via VIPP API.
 *
 * @param reversa_id - Reversa ID to track
 * @param tracking_code - Optional tracking code (if known)
 * @param authorization_code - Optional authorization code (if no tracking code)
 * @returns Tracking information and events
 */
export async function trackReversa(
  reversa_id?: string,
  tracking_code?: string,
  authorization_code?: string
): Promise<AgentCoreResponse<SGATrackReversaResponse>> {
  return invokeCarrierAgentCore<SGATrackReversaResponse>(
    {
      action: 'track_reversa',
      ...(reversa_id && { reversa_id }),
      ...(tracking_code && { tracking_code }),
      ...(authorization_code && { authorization_code }),
    },
    { useSession: false }
  );
}

/**
 * Send reversa e-ticket notification to technician via WhatsApp.
 * Uses Evolution API to send the message. Falls back to a wa.me link
 * if Evolution API is not configured or fails.
 *
 * @param phone - Technician's phone number
 * @param technician_name - Technician's name
 * @param authorization_code - E-ticket code
 * @param equipment_description - Description of equipment being returned
 * @param valid_until - Optional e-ticket expiration date
 * @param notes - Optional additional notes
 * @returns WhatsApp send result with fallback link
 */
export async function sendReversaWhatsApp(
  phone: string,
  technician_name: string,
  authorization_code: string,
  equipment_description: string,
  valid_until?: string,
  notes?: string
): Promise<AgentCoreResponse<SGASendReversaWhatsAppResponse>> {
  return invokeCarrierAgentCore<SGASendReversaWhatsAppResponse>(
    {
      action: 'send_reversa_whatsapp',
      phone,
      technician_name,
      authorization_code,
      equipment_description,
      ...(valid_until && { valid_until }),
      ...(notes && { notes }),
    },
    { useSession: false }
  );
}

/**
 * Generate a WhatsApp deep link for manual sharing.
 * Use this as a client-side fallback when Evolution API is unavailable.
 *
 * @param phone - Phone number (any format)
 * @param authorization_code - E-ticket code
 * @param equipment_description - Equipment description
 * @returns wa.me URL with pre-filled message
 */
export function generateWhatsAppLink(
  phone: string,
  authorization_code: string,
  equipment_description: string
): string {
  // Normalize phone number (remove non-digits)
  const normalized = phone.replace(/\D/g, '');

  // Build message
  const message = `Faiston - Logistica Reversa

Codigo de Autorizacao (E-Ticket): ${authorization_code}

Equipamento: ${equipment_description}

Instrucoes:
1. Va a qualquer agencia dos Correios
2. Informe o codigo de autorizacao acima
3. O envio sera gratuito (faturado para Faiston)`;

  // URL encode the message
  const encodedMessage = encodeURIComponent(message);

  return `https://wa.me/${normalized}?text=${encodedMessage}`;
}

// =============================================================================
// Tiflux Integration Functions (Phase 2 - Reversa)
// =============================================================================

/**
 * Get Tiflux tickets with "Em devolução" status for reversa processing.
 *
 * @returns List of tickets pending reversa
 */
export async function getTifluxTicketsForReversa(): Promise<
  AgentCoreResponse<GetTifluxTicketsResponse>
> {
  return invokeCarrierAgentCore<GetTifluxTicketsResponse>(
    {
      action: 'get_tiflux_tickets',
    },
    { useSession: false }
  );
}

/**
 * Get detailed Tiflux ticket with parsed technician data.
 *
 * @param ticketNumber - Tiflux ticket number
 * @returns Ticket detail with technician and equipment data
 */
export async function getTifluxTicketDetail(
  ticketNumber: string
): Promise<AgentCoreResponse<GetTifluxTicketDetailResponse>> {
  return invokeCarrierAgentCore<GetTifluxTicketDetailResponse>(
    {
      action: 'get_tiflux_ticket_detail',
      ticket_number: ticketNumber,
    },
    { useSession: false }
  );
}

/**
 * Get Tiflux tickets for expedicao (shipping) workflow.
 * Fetches tickets with stages "Enviado Logistica" or "Enviar Logistica".
 *
 * @returns List of tickets ready for shipping
 */
export async function getTifluxTicketsForExpedicao(): Promise<
  AgentCoreResponse<GetTifluxTicketsResponse>
> {
  return invokeCarrierAgentCore<GetTifluxTicketsResponse>(
    {
      action: 'get_tiflux_tickets_expedicao',
    },
    { useSession: false }
  );
}

// =============================================================================
// Tiflux DynamoDB Cache Functions (New - Background Sync)
// =============================================================================

/**
 * Default stage patterns for EXPEDICAO workflow.
 * These can be overridden by the caller.
 */
export const TIFLUX_EXPEDICAO_STAGES = ['Enviar Logistica', 'Enviado Logistica'];

/**
 * Default stage patterns for REVERSA workflow.
 * These can be overridden by the caller.
 */
export const TIFLUX_REVERSA_STAGES = ['Em devolução'];

/**
 * Sync result from tiflux sync operation.
 */
export interface TifluxSyncResult {
  success: boolean;
  workflow_type: string;
  stage_patterns: string[];
  fetched_from_tiflux: number;
  new_tickets_ingested: number;
  existing_tickets_skipped: number;
  with_parsed_data: number;
  errors: number;
}

/**
 * Cached tickets response from DynamoDB.
 */
export interface TifluxCachedTicketsResponse {
  success: boolean;
  tickets: Array<{
    ticket_number: number;
    title: string;
    status: string;
    status_id?: number;
    stage: string;
    stage_id?: number;
    desk?: string;
    desk_id?: number;
    client_name: string;
    created_at: string;
    updated_at?: string;
    workflow_type: 'EXPEDICAO' | 'REVERSA';
    requestor_name?: string;
    requestor_email?: string;
    // For EXPEDICAO - parsed destination address
    parsed_address?: {
      endereco: string;
      numero: string;
      complemento?: string;
      bairro: string;
      cidade: string;
      uf: string;
      cep: string;
    };
    // For REVERSA - parsed technician data
    parsed_technician?: {
      nome: string;
      telefone?: string;
      email?: string;
      endereco: string;
      numero: string;
      bairro: string;
      cidade: string;
      uf: string;
      cep: string;
    };
    equipment?: {
      description?: string;
      part_number?: string;
      serial_number?: string;
    };
    last_synced_at?: string;
  }>;
  count: number;
  workflow_type: string;
}

/**
 * Sync Tiflux tickets to DynamoDB cache.
 * This runs in background and syncs new tickets from Tiflux API to DynamoDB.
 *
 * @param workflowType - 'EXPEDICAO' or 'REVERSA'
 * @param stagePatterns - Stage names to filter by (case-insensitive)
 * @returns Sync result with counts
 */
export async function syncTifluxTickets(
  workflowType: 'EXPEDICAO' | 'REVERSA',
  stagePatterns?: string[]
): Promise<AgentCoreResponse<TifluxSyncResult>> {
  const patterns = stagePatterns || (workflowType === 'EXPEDICAO' ? TIFLUX_EXPEDICAO_STAGES : TIFLUX_REVERSA_STAGES);

  return invokeCarrierAgentCore<TifluxSyncResult>(
    {
      action: 'sync_tiflux_tickets',
      workflow_type: workflowType,
      stage_patterns: patterns,
    },
    { useSession: false }
  );
}

/**
 * Get cached Tiflux tickets from DynamoDB (fast, no API call to Tiflux).
 * Use this for instant UI loading, then sync in background.
 *
 * @param workflowType - 'EXPEDICAO' or 'REVERSA'
 * @returns Cached tickets from DynamoDB
 */
export async function getCachedTifluxTickets(
  workflowType: 'EXPEDICAO' | 'REVERSA'
): Promise<AgentCoreResponse<TifluxCachedTicketsResponse>> {
  return invokeCarrierAgentCore<TifluxCachedTicketsResponse>(
    {
      action: 'get_cached_tiflux_tickets',
      workflow_type: workflowType,
    },
    { useSession: false }
  );
}
