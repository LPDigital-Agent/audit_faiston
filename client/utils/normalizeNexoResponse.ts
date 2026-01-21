// =============================================================================
// NEXO Response Normalizer - BUG-022 v14 FIX
// =============================================================================
// Normalizes response structure to handle both top-level and nested paths.
//
// PROBLEM:
// Backend may return sheets/file_analysis at:
// - TOP LEVEL: { sheets: [...], file_analysis: {...} }  (error paths)
// - NESTED: { analysis: { sheets: [...] }, file_analysis: {...} }  (success path)
//
// SOLUTION:
// This function normalizes to the EXPECTED TypeScript contract (nested structure).
// Instead of patching each access point, normalize ONCE at entry.
// =============================================================================

import type { NexoAnalyzeFileResponse, NexoQuestion } from '@/services/sgaAgentcore';

// =============================================================================
// BUG-025 FIX: Question Validation Helpers
// =============================================================================

/**
 * Type guard to check if an object is a valid NexoQuestion.
 * BUG-025 FIX: Validates minimum required fields.
 */
function isValidQuestion(q: unknown): q is NexoQuestion {
  if (!q || typeof q !== 'object') {
    return false;
  }
  const qObj = q as Record<string, unknown>;

  // Must have question text
  if (!qObj.question || typeof qObj.question !== 'string') {
    return false;
  }

  return true;
}

/**
 * Validates and filters questions array.
 * BUG-025 FIX: Filters out malformed questions with console warnings.
 */
function validateQuestions(rawQuestions: unknown): NexoQuestion[] {
  if (!Array.isArray(rawQuestions)) {
    if (rawQuestions !== undefined && rawQuestions !== null) {
      console.error('[NEXO BUG-025] questions is not array:', typeof rawQuestions, rawQuestions);
    }
    return [];
  }

  const validQuestions = rawQuestions.filter((q, index) => {
    if (!isValidQuestion(q)) {
      console.warn('[NEXO BUG-025] Filtering invalid question at index', index, q);
      return false;
    }
    return true;
  });

  if (rawQuestions.length !== validQuestions.length) {
    console.warn('[NEXO BUG-025] Filtered invalid questions:', {
      raw: rawQuestions.length,
      valid: validQuestions.length,
      filtered: rawQuestions.length - validQuestions.length,
    });
  }

  return validQuestions as NexoQuestion[];
}

/**
 * Normalizes a potentially inconsistent NEXO response to match
 * the expected NexoAnalyzeFileResponse interface.
 *
 * BUG-022 v14 FIX: Handles both top-level and nested paths.
 * BUG-025 FIX: Validates and filters malformed questions.
 *
 * @param data - Raw response data from backend (potentially inconsistent structure)
 * @returns Normalized response matching TypeScript contract
 */
export function normalizeNexoResponse(data: unknown): NexoAnalyzeFileResponse {
  if (!data || typeof data !== 'object') {
    throw new Error('Invalid response: not an object');
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const d = data as Record<string, any>;

  // Extract analysis object - check nested first, then build from top-level
  const existingAnalysis = d.analysis || {};

  // Extract sheets from top-level OR nested in analysis
  // Priority: existing nested > top-level sheets > empty array
  const sheets = existingAnalysis.sheets || d.sheets || [];

  // Extract other analysis fields with fallbacks
  const sheetCount = existingAnalysis.sheet_count ??
    d.sheet_count ??
    (Array.isArray(sheets) ? sheets.length : 0);

  const totalRows = existingAnalysis.total_rows ?? d.total_rows ?? 0;

  const recommendedStrategy = existingAnalysis.recommended_strategy ??
    d.recommended_strategy ??
    'manual_review';

  // Build normalized analysis object (always nested structure)
  const normalizedAnalysis = {
    sheets: Array.isArray(sheets) ? sheets : [],
    sheet_count: Number(sheetCount) || 0,
    total_rows: Number(totalRows) || 0,
    recommended_strategy: String(recommendedStrategy),
  };

  // Return normalized response matching TypeScript interface
  return {
    success: Boolean(d.success),
    error: d.error as string | undefined,
    import_session_id: String(d.import_session_id || ''),
    filename: String(d.filename || ''),
    detected_file_type: String(d.detected_file_type || 'unknown'),

    // CRITICAL: Always use nested structure
    analysis: normalizedAnalysis,

    column_mappings: Array.isArray(d.column_mappings) ? d.column_mappings : [],
    overall_confidence: Number(d.overall_confidence) || 0,

    // BUG-025 FIX: Validate and filter questions before returning
    questions: validateQuestions(d.questions),
    // NOTE: unmapped_questions has a different type than NexoQuestion[],
    // so we pass it through as-is (array check only)
    unmapped_questions: Array.isArray(d.unmapped_questions) && d.unmapped_questions.length > 0
      ? d.unmapped_questions
      : undefined,
    reasoning_trace: Array.isArray(d.reasoning_trace) ? d.reasoning_trace : [],
    user_id: d.user_id as string | undefined,
    session_id: d.session_id as string | undefined,
    session_state: d.session_state,
  };
}

/**
 * Validates that a response has the minimum required data for analysis.
 *
 * BUG-020 v6 FIX: Checks BOTH top-level and nested paths.
 * This replaces the previous check that only looked at nested paths.
 *
 * @param data - Response data to validate
 * @returns true if response has valid analysis data
 */
export function hasValidAnalysisData(data: unknown): boolean {
  if (!data || typeof data !== 'object') {
    return false;
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const d = data as Record<string, any>;

  // Check for sheets at top level OR nested
  const hasSheets =
    'sheets' in d ||
    (d.analysis && typeof d.analysis === 'object' && 'sheets' in d.analysis);

  // Check for file_analysis at top level OR nested
  const hasFileAnalysis =
    'file_analysis' in d ||
    (d.analysis && typeof d.analysis === 'object' && 'file_analysis' in d.analysis);

  // Check for column_mappings (another indicator of valid response)
  const hasColumnMappings = 'column_mappings' in d;

  // Valid if any of these structures exist
  return hasSheets || hasFileAnalysis || hasColumnMappings;
}
