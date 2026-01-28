// =============================================================================
// useSmartImporter Hook - SGA Inventory Module
// =============================================================================
// Universal file importer with auto-detection.
// Handles file upload, type detection, and routes to appropriate processor.
//
// Philosophy: Observe -> Think -> Learn -> Act
// The hook OBSERVES the file, THINKS about its type, LEARNS from detection,
// and ACTS by routing to the appropriate backend agent.
//
// NEXO Integration (Agentic AI-First):
// Optionally uses the NEXO intelligent import flow with:
// - Multi-sheet XLSX analysis
// - Clarification questions when uncertain
// - Learning from user answers for future imports
// - Explicit reasoning trace for transparency
// =============================================================================


import { useState, useCallback, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getNFUploadUrl,
  invokeSmartImport,
  confirmNFEntry,
  getPendingNFEntries,
  assignProjectToEntry,
  clearSGASession,
  // NEXO Intelligent Import
  nexoAnalyzeFile,
  nexoSubmitAnswers,
  type NexoQuestion,
  type NexoColumnMapping,
  type NexoReasoningStep,
  type NexoSheetAnalysis,
  type NexoSessionState,  // STATELESS: Full session state type
  type SGAGetUploadUrlResponse,  // BUG-014: Type for extraction
} from '@/services/sgaAgentcore';
import { extractAgentResponse, safeExtractErrorMessage, type DebugAnalysis } from '@/utils/agentcoreResponse';  // BUG-014/BUG-022: A2A response extraction
import { normalizeNexoResponse } from '@/utils/normalizeNexoResponse';  // BUG-022 v14
import { AgentCoreError } from '@/services/agentcoreBase';  // BUG-027: Custom error with debug_analysis
import type {
  SmartFileType,
  SmartSourceType,
  SmartImportPreview,
  SmartImportProgress,
  UseSmartImporterReturn,
  SmartImportUploadResponse,
  EnrichedError,  // BUG-027: Import from types (centralized definition)
} from '@/lib/ativos/smartImportTypes';
import {
  detectFileTypeFromFile,
  validateSmartImportFile,
  isNFImportResult,
  isSpreadsheetImportResult,
  isTextImportResult,
  getFileTypeLabel,
} from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Constants
// =============================================================================

const INITIAL_PROGRESS: SmartImportProgress = {
  stage: 'idle',
  percent: 0,
  message: '',
};

// Query key for pending entries
const PENDING_ENTRIES_KEY = 'sga-pending-nf-entries';

// =============================================================================
// NEXO Analysis State Types
// =============================================================================

export interface NexoAnalysisState {
  sessionId: string | null;
  sessionState: NexoSessionState | null;  // STATELESS: Full session state
  isAnalyzing: boolean;
  sheets: NexoSheetAnalysis[];
  columnMappings: NexoColumnMapping[];
  questions: NexoQuestion[];
  answers: Record<string, string>;
  reasoningTrace: NexoReasoningStep[];
  overallConfidence: number;
  error: string | null;
}

const INITIAL_NEXO_STATE: NexoAnalysisState = {
  sessionId: null,
  sessionState: null,  // STATELESS: Full session state
  isAnalyzing: false,
  sheets: [],
  columnMappings: [],
  questions: [],
  answers: {},
  reasoningTrace: [],
  overallConfidence: 0,
  error: null,
};

// =============================================================================
// Hook
// =============================================================================

export function useSmartImporter(): UseSmartImporterReturn & {
  // NEXO Intelligent Import (Agentic AI-First)
  nexoState: NexoAnalysisState;
  useNexoFlow: boolean;
  setUseNexoFlow: (enabled: boolean) => void;
  uploadWithNexoAnalysis: (file: File) => Promise<NexoAnalysisState>;
  answerNexoQuestion: (questionId: string, answer: string) => void;
  submitNexoAnswers: () => Promise<void>;
  hasNexoQuestions: boolean;
  isNexoReady: boolean;
} {
  const queryClient = useQueryClient();

  // Detection state
  const [detectedType, setDetectedType] = useState<SmartFileType | null>(null);

  // NEXO Intelligent Import state
  const [useNexoFlow, setUseNexoFlow] = useState(false);
  const [nexoState, setNexoState] = useState<NexoAnalysisState>(INITIAL_NEXO_STATE);

  // Fetch pending entries (reuse same key as useNFReader for cache sharing)
  const {
    data: pendingEntriesData,
    isLoading: pendingEntriesLoading,
    refetch: refreshPendingEntries,
  } = useQuery({
    queryKey: [PENDING_ENTRIES_KEY],
    queryFn: async () => {
      const result = await getPendingNFEntries();
      return result.data.entries;
    },
    staleTime: 60000, // 1 minute
    retry: 1,
  });

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState<SmartImportProgress>(INITIAL_PROGRESS);
  // BUG-027 FIX: Use EnrichedError to preserve debug_analysis for DebugAnalysisPanel
  const [error, setError] = useState<EnrichedError | null>(null);

  // Result state
  const [preview, setPreview] = useState<SmartImportPreview | null>(null);
  const [response, setResponse] = useState<SmartImportUploadResponse | null>(null);

  /**
   * Upload file and process with smart import.
   * Auto-detects file type and routes to appropriate agent.
   * projectId and locationId are optional - can be set in preview after analysis.
   */
  const uploadAndProcess = useCallback(async (
    file: File,
    projectId: string | null,
    locationId: string | null
  ): Promise<SmartImportPreview> => {
    setIsProcessing(true);
    setError(null);
    setPreview(null);
    setResponse(null);
    setProgress({ stage: 'detecting', percent: 5, message: 'Detectando tipo de arquivo...' });

    // IMPORTANT: Clear session to force cold start with latest deployed code
    // AgentCore warm instances cache old code - new session ID forces new instance
    clearSGASession();
    console.log('[SmartImporter] Session cleared - forcing cold start');

    try {
      // =======================================================================
      // OBSERVE: Validate and detect file type (client-side heuristic)
      // =======================================================================
      const validationError = validateSmartImportFile(file);
      if (validationError) {
        throw new Error(validationError);
      }

      const fileType = detectFileTypeFromFile(file);
      setDetectedType(fileType);
      setProgress({
        stage: 'detecting',
        percent: 10,
        message: `Tipo detectado: ${getFileTypeLabel(fileType)}`,
      });

      if (fileType === 'unknown') {
        throw new Error('Formato de arquivo não suportado');
      }

      // =======================================================================
      // THINK: Get presigned URL for upload
      // =======================================================================
      setProgress({ stage: 'uploading', percent: 20, message: 'Obtendo URL de upload...' });

      const contentType = file.type || getContentTypeForFileType(fileType);
      const urlResult = await getNFUploadUrl({
        filename: file.name,
        content_type: contentType,
      });

      // BUG-014: Extract response from A2A wrapped format
      const uploadUrlData = extractAgentResponse<SGAGetUploadUrlResponse>(urlResult.data);

      // Defensive validation - ensure we got a valid response
      if (!uploadUrlData || !uploadUrlData.upload_url || !uploadUrlData.s3_key) {
        // BUG-022 FIX: Use safeExtractErrorMessage to handle double-encoded errors
        const rawError = (uploadUrlData as { error?: string })?.error || 'Falha ao obter URL de upload';
        const errorMsg = safeExtractErrorMessage(rawError);
        throw new Error(errorMsg);
      }

      // =======================================================================
      // LEARN: Upload file to S3
      // CRITICAL: Use required_headers from backend - these values are signed into the presigned URL
      // Any header mismatch causes 403 Forbidden (signature validation failure)
      // =======================================================================
      setProgress({ stage: 'uploading', percent: 40, message: 'Enviando arquivo...' });

      const uploadHeaders = uploadUrlData.required_headers || { 'Content-Type': contentType };
      const uploadResponse = await fetch(uploadUrlData.upload_url, {
        method: 'PUT',
        body: file,
        headers: uploadHeaders,
      });

      if (!uploadResponse.ok) {
        throw new Error('Falha no upload do arquivo');
      }

      // =======================================================================
      // ACT: Call smart import (backend will detect and route)
      // =======================================================================
      setProgress({ stage: 'processing', percent: 70, message: 'Processando arquivo...' });

      const smartResult = await invokeSmartImport({
        s3_key: uploadUrlData.s3_key,
        filename: file.name,
        content_type: contentType,
        project_id: projectId || undefined,
        destination_location_id: locationId || undefined,
      });

      // =======================================================================
      // Complete: Set result state
      // =======================================================================
      setProgress({ stage: 'complete', percent: 100, message: 'Processamento concluído!' });

      // DEBUG: Log the actual response to diagnose modal issue
      console.log('[SmartImporter] Raw smartResult:', JSON.stringify(smartResult, null, 2));
      console.log('[SmartImporter] smartResult.data:', smartResult.data);
      console.log('[SmartImporter] smartResult.data.preview:', smartResult.data?.preview);
      console.log('[SmartImporter] smartResult.data.source_type:', smartResult.data?.source_type);

      // Handle both OLD format (no preview wrapper) and NEW format (with preview wrapper)
      // OLD: { source_type, items, ... } directly
      // NEW: { success, preview: { source_type, items, ... } }
      const responseData = smartResult.data;
      const previewResult = responseData?.preview ||
        (responseData?.source_type ? responseData as unknown as SmartImportPreview : null);

      console.log('[SmartImporter] Resolved previewResult:', previewResult);

      setPreview(previewResult);
      setResponse(smartResult.data);

      // AUDIT-002: Check for application-level errors in successful HTTP responses
      // Backend may return HTTP 200 with { success: false, error: "...", debug_analysis: {...} }
      const responseAny = responseData as unknown as Record<string, unknown>;
      if (responseAny?.success === false && responseAny?.error) {
        // Cast DebugAnalysisBase to DebugAnalysis (base type is subset)
        const debugAnalysis = smartResult.debug_analysis as DebugAnalysis | undefined;
        const errorMsg = safeExtractErrorMessage(responseAny.error as string);
        console.log('[SmartImporter] AUDIT-002: Application error with debug_analysis:', debugAnalysis);
        setError({ message: errorMsg, debug_analysis: debugAnalysis });
        setProgress({ stage: 'error', percent: 0, message: errorMsg });
        throw new Error(errorMsg);
      }

      // Update detected type from backend (more reliable)
       
      const detectedType = smartResult.data?.detected_type ||
        (previewResult as unknown as Record<string, unknown>)?.detected_file_type as SmartFileType | undefined;
      setDetectedType(detectedType || null);

      return previewResult;
    } catch (err) {
      // BUG-022 FIX: Use safeExtractErrorMessage to handle double-encoded error messages
      const rawMessage = err instanceof Error ? err.message : 'Erro ao processar arquivo';
      const message = safeExtractErrorMessage(rawMessage);

      // BUG-027 FIX: Extract debug_analysis from AgentCoreError
      let debugAnalysis: DebugAnalysis | undefined;
      if (err instanceof AgentCoreError && err.debug_analysis) {
        debugAnalysis = err.debug_analysis;
        console.log('[SmartImporter] BUG-027: Extracted debug_analysis from error');
      }

      setError({ message, debug_analysis: debugAnalysis });
      setProgress({ stage: 'error', percent: 0, message });
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  /**
   * Clear preview and reset state.
   */
  const clearPreview = useCallback(() => {
    setPreview(null);
    setResponse(null);
    setDetectedType(null);
    setError(null);
    setProgress(INITIAL_PROGRESS);
  }, []);

  /**
   * Confirm entry and create movements.
   * Implementation varies based on source_type.
   */
  const confirmEntry = useCallback(async () => {
    if (!preview) {
      throw new Error('Nenhum preview disponível para confirmar');
    }

    // Confirm based on source type
    if (isNFImportResult(preview)) {
      // NF confirmation
      const result = await confirmNFEntry({
        entry_id: preview.entry_id,
        item_mappings: preview.suggested_mappings,
        notes: undefined,
      });

      if (!result.data.success) {
        throw new Error(result.data.errors?.join(', ') || 'Erro ao confirmar entrada');
      }

      // Invalidate queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
      queryClient.invalidateQueries({ queryKey: ['sga-pending-nf-entries'] });

      clearPreview();
      return;
    }

    if (isSpreadsheetImportResult(preview)) {
      // Spreadsheet confirmation - TODO: Call executeImport
      // For now, just clear preview
      console.warn('Spreadsheet confirmation not yet implemented');
      clearPreview();
      return;
    }

    if (isTextImportResult(preview)) {
      // Text import always requires HIL - cannot auto-confirm
      throw new Error('Importações de texto requerem revisão manual antes de confirmar');
    }

    throw new Error('Tipo de preview desconhecido');
  }, [preview, queryClient, clearPreview]);

  /**
   * Assign a project to a pending entry.
   */
  const assignProject = useCallback(async (entryId: string, projectId: string): Promise<void> => {
    try {
      await assignProjectToEntry(entryId, projectId);
      // Invalidate pending entries to refresh the list
      queryClient.invalidateQueries({ queryKey: [PENDING_ENTRIES_KEY] });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao atribuir projeto';
      throw new Error(message);
    }
  }, [queryClient]);

  // ===========================================================================
  // NEXO Intelligent Import Functions (Agentic AI-First)
  // ===========================================================================

  /**
   * Upload file with NEXO intelligent analysis.
   * Uses ReAct pattern: OBSERVE → THINK → ASK → LEARN → ACT
   */
  const uploadWithNexoAnalysis = useCallback(async (file: File): Promise<NexoAnalysisState> => {
    setNexoState(prev => ({ ...prev, isAnalyzing: true, error: null }));
    setIsProcessing(true);
    setError(null);
    setProgress({ stage: 'detecting', percent: 5, message: 'NEXO analisando arquivo...' });

    clearSGASession();

    try {
      // Validate file
      const validationError = validateSmartImportFile(file);
      if (validationError) {
        throw new Error(validationError);
      }

      const fileType = detectFileTypeFromFile(file);
      setDetectedType(fileType);
      setProgress({ stage: 'uploading', percent: 20, message: 'Obtendo URL de upload...' });

      // Get presigned URL
      const contentType = file.type || getContentTypeForFileType(fileType);
      const urlResult = await getNFUploadUrl({
        filename: file.name,
        content_type: contentType,
      });

      // BUG-014: Extract response from A2A wrapped format
      const uploadUrlDataNexo = extractAgentResponse<SGAGetUploadUrlResponse>(urlResult.data);

      if (!uploadUrlDataNexo?.upload_url || !uploadUrlDataNexo?.s3_key) {
        throw new Error('Falha ao obter URL de upload');
      }

      // Upload to S3
      // CRITICAL: Use required_headers from backend - these values are signed into the presigned URL
      setProgress({ stage: 'uploading', percent: 40, message: 'Enviando arquivo...' });
      const uploadHeadersNexo = uploadUrlDataNexo.required_headers || { 'Content-Type': contentType };
      const uploadResponse = await fetch(uploadUrlDataNexo.upload_url, {
        method: 'PUT',
        body: file,
        headers: uploadHeadersNexo,
      });

      if (!uploadResponse.ok) {
        throw new Error('Falha no upload do arquivo');
      }

      // NEXO Analysis (OBSERVE + THINK)
      setProgress({ stage: 'processing', percent: 60, message: 'NEXO analisando estrutura...' });

      const analysisResult = await nexoAnalyzeFile({
        s3_key: uploadUrlDataNexo.s3_key,
        filename: file.name,
        content_type: contentType,
      });

      if (!analysisResult.data?.success) {
        throw new Error('Falha na análise NEXO');
      }

      // BUG-022 v14 FIX: Normalize response to consistent NESTED structure
      // This ensures all data accesses work regardless of backend response format
      const rawData = analysisResult.data;
      const data = normalizeNexoResponse(rawData);
      console.log('[SmartImporter] BUG-022 v14: Normalized response structure');

      // STATELESS: Build session state from response (or use returned session_state)
      // NOTE: stage MUST be a valid Python ImportStage enum value:
      // analyzing, reasoning, questioning, awaiting, learning, processing, complete
      const sessionState: NexoSessionState = data.session_state || {
        session_id: data.import_session_id,
        filename: file.name,
        s3_key: uploadUrlDataNexo.s3_key,
        stage: data.questions && data.questions.length > 0 ? 'questioning' : 'processing',
        // BUG-022 v14: Using normalized data - structure is guaranteed
        file_analysis: {
          sheets: data.analysis.sheets,
          sheet_count: data.analysis.sheet_count,
          total_rows: data.analysis.total_rows,
          detected_type: data.detected_file_type,
          recommended_strategy: data.analysis.recommended_strategy,
        },
        reasoning_trace: data.reasoning_trace || [],
        questions: data.questions || [],
        answers: {},
        learned_mappings: {},
        // FIX (January 2026): Initialize ai_instructions for "Outros:" answers
        ai_instructions: {},
        // FEATURE (January 2026): Initialize requested_new_columns for dynamic schema
        requested_new_columns: [],
        column_mappings: data.column_mappings.reduce((acc, m) => {
          acc[m.file_column] = m.target_field;
          return acc;
        }, {} as Record<string, string>),
        // NOTE: confidence format MUST match Python ConfidenceScore dataclass:
        // overall, extraction_quality, evidence_strength, historical_match, risk_level, factors, requires_hil
        confidence: {
          overall: data.overall_confidence,
          extraction_quality: 1.0,
          evidence_strength: 1.0,
          historical_match: 1.0,
          risk_level: data.overall_confidence >= 0.8 ? 'low' : data.overall_confidence >= 0.5 ? 'medium' : 'high',
          factors: [],
          requires_hil: data.overall_confidence < 0.6,
        },
        error: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Update NEXO state (using normalized data - structure is guaranteed)
      const newNexoState: NexoAnalysisState = {
        sessionId: data.import_session_id,
        sessionState,  // STATELESS: Store full session state
        isAnalyzing: false,
        sheets: data.analysis.sheets,
        columnMappings: data.column_mappings,
        questions: data.questions || [],
        answers: {},
        reasoningTrace: data.reasoning_trace || [],
        overallConfidence: data.overall_confidence,
        error: null,
      };

      setNexoState(newNexoState);
      setProgress({ stage: 'complete', percent: 100, message: 'Análise NEXO concluída!' });

      return newNexoState;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro na análise NEXO';

      // BUG-027 FIX: Extract debug_analysis from AgentCoreError
      let debugAnalysis: DebugAnalysis | undefined;
      if (err instanceof AgentCoreError && err.debug_analysis) {
        debugAnalysis = err.debug_analysis;
        console.log('[SmartImporter] BUG-027: Extracted debug_analysis from NEXO error');
      }

      setNexoState(prev => ({ ...prev, isAnalyzing: false, error: message }));
      setError({ message, debug_analysis: debugAnalysis });
      setProgress({ stage: 'error', percent: 0, message });
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  /**
   * Answer a NEXO clarification question.
   */
  const answerNexoQuestion = useCallback((questionId: string, answer: string) => {
    setNexoState(prev => ({
      ...prev,
      answers: { ...prev.answers, [questionId]: answer },
    }));
  }, []);

  /**
   * Submit all NEXO answers and get updated analysis.
   * STATELESS ARCHITECTURE: Passes full session state to backend.
   */
  const submitNexoAnswers = useCallback(async () => {
    if (!nexoState.sessionState) {
      throw new Error('Nenhuma sessão NEXO ativa');
    }

    setNexoState(prev => ({ ...prev, isAnalyzing: true }));

    try {
      // STATELESS: Merge current answers into session state before sending
      const updatedSessionState: NexoSessionState = {
        ...nexoState.sessionState,
        answers: { ...nexoState.sessionState.answers, ...nexoState.answers },
        updated_at: new Date().toISOString(),
      };

      const result = await nexoSubmitAnswers({
        session_state: updatedSessionState,  // STATELESS: Pass full state
        answers: nexoState.answers,
      });

      if (!result.data?.success) {
        throw new Error('Falha ao processar respostas');
      }

      // STATELESS: Update session state from backend response
      const newSessionState = result.data.session || updatedSessionState;

      setNexoState(prev => ({
        ...prev,
        isAnalyzing: false,
        sessionState: newSessionState,  // STATELESS: Store updated state
        questions: result.data!.remaining_questions || [],
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao processar respostas';
      setNexoState(prev => ({ ...prev, isAnalyzing: false, error: message }));
      throw err;
    }
  }, [nexoState.sessionState, nexoState.answers]);

  /**
   * Check if NEXO has unanswered questions.
   */
  const hasNexoQuestions = useMemo(() => {
    const criticalQuestions = nexoState.questions.filter(q => q.importance === 'critical');
    const unansweredCritical = criticalQuestions.filter(q => !nexoState.answers[q.id]);
    return unansweredCritical.length > 0;
  }, [nexoState.questions, nexoState.answers]);

  /**
   * Check if NEXO is ready to proceed with import.
   */
  const isNexoReady = useMemo(() => {
    return (
      nexoState.sessionId !== null &&
      !nexoState.isAnalyzing &&
      !hasNexoQuestions &&
      nexoState.error === null
    );
  }, [nexoState.sessionId, nexoState.isAnalyzing, hasNexoQuestions, nexoState.error]);

  return {
    detectedType,
    isProcessing,
    progress,
    error,
    preview,
    response,
    uploadAndProcess,
    clearPreview,
    confirmEntry,
    // Pending entries support
    pendingEntries: pendingEntriesData ?? [],
    pendingEntriesLoading,
    refreshPendingEntries,
    assignProject,
    // NEXO Intelligent Import (Agentic AI-First)
    nexoState,
    useNexoFlow,
    setUseNexoFlow,
    uploadWithNexoAnalysis,
    answerNexoQuestion,
    submitNexoAnswers,
    hasNexoQuestions,
    isNexoReady,
  };
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Get MIME content type for a detected file type.
 */
function getContentTypeForFileType(fileType: SmartFileType): string {
  const contentTypeMap: Record<SmartFileType, string> = {
    xml: 'application/xml',
    pdf: 'application/pdf',
    image: 'image/jpeg',
    csv: 'text/csv',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    txt: 'text/plain',
    unknown: 'application/octet-stream',
  };

  return contentTypeMap[fileType] || 'application/octet-stream';
}

// =============================================================================
// Re-export types for convenience
// =============================================================================

export type {
  SmartFileType,
  SmartSourceType,
  SmartImportPreview,
  SmartImportProgress,
  UseSmartImporterReturn,
  SmartImportUploadResponse,
  EnrichedError,  // BUG-027: Re-export for DebugAnalysisPanel integration
};

export {
  detectFileTypeFromFile,
  validateSmartImportFile,
  requiresHILReview,
  isNFImportResult,
  isSpreadsheetImportResult,
  isTextImportResult,
  getFileTypeLabel,
  SMART_IMPORT_FORMATS,
} from '@/lib/ativos/smartImportTypes';

// NEXO types re-export (from sgaAgentcore.ts)
export type {
  NexoQuestion,
  NexoColumnMapping,
  NexoReasoningStep,
  NexoSheetAnalysis,
};
