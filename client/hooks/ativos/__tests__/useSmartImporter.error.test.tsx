/**
 * SmartImporter Error Handling Tests - BUG-027
 *
 * Tests the error enrichment flow from Debug Agent to DebugAnalysisPanel.
 * Validates that:
 * 1. AgentCoreError with debug_analysis is properly extracted
 * 2. EnrichedError type matches DebugAnalysisPanel interface
 * 3. All 7 error scenarios from Phase 5 plan are covered
 *
 * @see docs/plans/hidden-bouncing-penguin.md Phase 5.3
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useSmartImporter, type EnrichedError } from '../useSmartImporter';
import { AgentCoreError } from '@/services/agentcoreBase';
import type { DebugAnalysis } from '@/utils/agentcoreResponse';

// =============================================================================
// Mock Setup
// =============================================================================

// Mock the sgaAgentcore service
vi.mock('@/services/sgaAgentcore', () => ({
  getNFUploadUrl: vi.fn(),
  invokeSmartImport: vi.fn(),
  confirmNFEntry: vi.fn(),
  getPendingNFEntries: vi.fn().mockResolvedValue({ data: { entries: [] } }),
  assignProjectToEntry: vi.fn(),
  clearSGASession: vi.fn(),
  nexoAnalyzeFile: vi.fn(),
  nexoSubmitAnswers: vi.fn(),
  nexoLearnFromImport: vi.fn(),
  nexoPrepareProcessing: vi.fn(),
}));

// Import mocked functions for control
import {
  getNFUploadUrl,
  invokeSmartImport,
  nexoAnalyzeFile,
} from '@/services/sgaAgentcore';

// =============================================================================
// Test Fixtures
// =============================================================================

/**
 * Creates a mock DebugAnalysis object matching the Debug Agent output.
 * This is the structure that DebugAnalysisPanel expects.
 */
function createMockDebugAnalysis(overrides: Partial<DebugAnalysis> = {}): DebugAnalysis {
  return {
    error_signature: 'sig_test_abc123',
    error_type: 'ValidationError',
    recoverable: true,
    technical_explanation: 'Análise técnica do erro para debug.',
    root_causes: [
      {
        cause: 'Arquivo CSV com encoding incorreto',
        confidence: 0.85,
        source: 'inference',
        evidence: ['Header com caracteres especiais detectados'],
      },
    ],
    debugging_steps: [
      'Verificar encoding do arquivo (UTF-8 esperado)',
      'Verificar delimitador (vírgula vs ponto-e-vírgula)',
    ],
    documentation_links: [
      {
        title: 'CSV Import Guide',
        url: 'https://docs.faiston.com/csv-import',
        relevance: 'Guia de importação CSV',
      },
    ],
    similar_patterns: [],
    suggested_action: 'retry',
    llm_powered: true,
    ...overrides,
  };
}

/**
 * Creates a mock File object for testing.
 */
function createMockFile(name: string, type: string, size: number = 1024): File {
  const content = new Array(size).fill('x').join('');
  return new File([content], name, { type });
}

/**
 * Creates a valid upload URL response.
 */
function createMockUploadUrlResponse() {
  return {
    data: {
      upload_url: 'https://s3.amazonaws.com/bucket/test-key?signed=true',
      s3_key: 'uploads/test-key.csv',
      expires_in: 3600,
    },
    sessionId: 'mock-session-id',
  };
}

// =============================================================================
// Test Wrapper
// =============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

// =============================================================================
// Test Suite: Error Enrichment Flow
// =============================================================================

describe('useSmartImporter Error Handling (BUG-027)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock successful fetch for S3 upload
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
  });

  describe('AgentCoreError Extraction', () => {
    it('should extract debug_analysis from AgentCoreError', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'ValidationError',
        suggested_action: 'retry',
      });

      // AgentCoreError constructor: (message, { debug_analysis, status, originalResponse })
      const agentCoreError = new AgentCoreError(
        'Arquivo CSV inválido',
        {
          status: 400,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(agentCoreError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      const mockFile = createMockFile('test.csv', 'text/csv');

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(mockFile, null, null);
        } catch {
          // Expected to throw
        }
      });

      // Assert
      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toBe('Arquivo CSV inválido');
      expect(result.current.error?.debug_analysis).toBeDefined();
      expect(result.current.error?.debug_analysis?.error_type).toBe('ValidationError');
      expect(result.current.error?.debug_analysis?.suggested_action).toBe('retry');
    });

    it('should handle errors without debug_analysis gracefully', async () => {
      // Arrange
      const regularError = new Error('Network error');

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(regularError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      const mockFile = createMockFile('test.csv', 'text/csv');

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(mockFile, null, null);
        } catch {
          // Expected to throw
        }
      });

      // Assert
      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.message).toBe('Network error');
      expect(result.current.error?.debug_analysis).toBeUndefined();
    });
  });

  describe('EnrichedError Type Compatibility', () => {
    it('should produce EnrichedError compatible with DebugAnalysisPanel', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_signature: 'sig_panel_test',
        root_causes: [
          {
            cause: 'Test root cause',
            confidence: 0.9,
            source: 'memory_pattern',
            evidence: ['Evidence 1', 'Evidence 2'],
          },
        ],
        debugging_steps: ['Step 1', 'Step 2', 'Step 3'],
        documentation_links: [
          {
            title: 'Test Doc',
            url: 'https://example.com',
            relevance: 'High relevance',
          },
        ],
      });

      const agentCoreError = new AgentCoreError(
        'Test error',
        {
          status: 500,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(agentCoreError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      const mockFile = createMockFile('test.csv', 'text/csv');

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(mockFile, null, null);
        } catch {
          // Expected to throw
        }
      });

      // Assert - Verify all DebugAnalysisPanel required fields
      const error = result.current.error as EnrichedError;
      const analysis = error.debug_analysis as DebugAnalysis;

      expect(analysis.error_signature).toBe('sig_panel_test');
      expect(analysis.error_type).toBeDefined();
      expect(analysis.recoverable).toBeDefined();
      expect(analysis.technical_explanation).toBeDefined();
      expect(analysis.root_causes).toHaveLength(1);
      expect(analysis.root_causes[0].cause).toBe('Test root cause');
      expect(analysis.root_causes[0].confidence).toBe(0.9);
      expect(analysis.root_causes[0].source).toBe('memory_pattern');
      expect(analysis.root_causes[0].evidence).toHaveLength(2);
      expect(analysis.debugging_steps).toHaveLength(3);
      expect(analysis.documentation_links).toHaveLength(1);
      expect(analysis.suggested_action).toBeDefined();
      expect(analysis.llm_powered).toBeDefined();
    });
  });

  // ===========================================================================
  // Phase 5.1 Scenarios: All 7 Error Types
  // ===========================================================================

  describe('Phase 5 Error Scenarios', () => {
    /**
     * Scenario 1: HTTP 424 (cold start / failed dependency)
     * Expected: Debug Agent provides detailed explanation, not blank message
     */
    it('Scenario 1: HTTP 424 cold start error - should have detailed message', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'DependencyError',
        technical_explanation: 'O serviço AgentCore está inicializando (cold start). ' +
          'Isso ocorre quando a função Lambda precisa ser carregada na memória pela primeira vez.',
        suggested_action: 'retry',
        recoverable: true,
      });

      const coldStartError = new AgentCoreError(
        'Serviço temporariamente indisponível',
        {
          status: 424,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(coldStartError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('test.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert - Message should NOT be blank
      expect(result.current.error?.message).not.toBe('');
      expect(result.current.error?.message.length).toBeGreaterThan(10);
      expect(result.current.error?.debug_analysis?.error_type).toBe('DependencyError');
      expect(result.current.error?.debug_analysis?.technical_explanation).toContain('cold start');
    });

    /**
     * Scenario 2: Malformed CSV
     * Expected: AI-powered root cause analysis
     */
    it('Scenario 2: Malformed CSV - should provide AI root cause analysis', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'ValidationError',
        technical_explanation: 'O arquivo CSV contém caracteres inválidos no header. ' +
          'Encoding detectado: ISO-8859-1, esperado: UTF-8.',
        root_causes: [
          {
            cause: 'Encoding incorreto do arquivo',
            confidence: 0.92,
            source: 'inference',
            evidence: ['Caractere 0xE7 detectado na linha 1'],
          },
        ],
        llm_powered: true,
      });

      const csvError = new AgentCoreError(
        'Formato de CSV inválido',
        {
          status: 400,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(csvError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('malformed.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert - Should have AI-powered analysis
      expect(result.current.error?.debug_analysis?.llm_powered).toBe(true);
      expect(result.current.error?.debug_analysis?.root_causes.length).toBeGreaterThan(0);
    });

    /**
     * Scenario 3: Invalid XML (NF-e)
     * Expected: Technical explanation in pt-BR
     */
    it('Scenario 3: Invalid XML - should have pt-BR technical explanation', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'XMLParseError',
        technical_explanation: 'O XML da NF-e está malformado. ' +
          'Tag <infNFe> não encontrada na estrutura esperada.',
        suggested_action: 'abort',
      });

      const xmlError = new AgentCoreError(
        'XML da NF-e inválido',
        {
          status: 400,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(xmlError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('invalid.xml', 'application/xml'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert - Technical explanation should be in Portuguese
      const explanation = result.current.error?.debug_analysis?.technical_explanation || '';
      expect(explanation).toContain('NF-e');
      // Check for Portuguese words
      expect(explanation).toMatch(/malformado|inválido|encontrada|estrutura/i);
    });

    /**
     * Scenario 4: Auth error (expired Cognito token)
     * Expected: "escalate" suggested action
     */
    it('Scenario 4: Auth error - should suggest escalate action', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'AuthenticationError',
        technical_explanation: 'Token de autenticação expirado ou inválido.',
        suggested_action: 'escalate',
        recoverable: false,
      });

      const authError = new AgentCoreError(
        'Não autorizado',
        {
          status: 401,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockRejectedValue(authError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('test.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(result.current.error?.debug_analysis?.suggested_action).toBe('escalate');
      expect(result.current.error?.debug_analysis?.recoverable).toBe(false);
    });

    /**
     * Scenario 5: Timeout (large file processing)
     * Expected: "retry" suggested action
     */
    it('Scenario 5: Timeout error - should suggest retry action', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'TimeoutError',
        technical_explanation: 'O processamento excedeu o tempo limite. ' +
          'Arquivos maiores podem requerer mais tempo.',
        suggested_action: 'retry',
        recoverable: true,
        debugging_steps: [
          'Dividir arquivo em partes menores',
          'Tentar novamente em horário de menor uso',
        ],
      });

      const timeoutError = new AgentCoreError(
        'Timeout no processamento',
        {
          status: 504,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(timeoutError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('large.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 10 * 1024 * 1024),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(result.current.error?.debug_analysis?.suggested_action).toBe('retry');
      expect(result.current.error?.debug_analysis?.recoverable).toBe(true);
      expect(result.current.error?.debug_analysis?.debugging_steps.length).toBeGreaterThan(0);
    });

    /**
     * Scenario 6: Database error (invalid FK reference)
     * Expected: Debugging steps provided
     */
    it('Scenario 6: Database error - should provide debugging steps', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'DatabaseError',
        technical_explanation: 'Violação de chave estrangeira. ' +
          'O part_number referenciado não existe na tabela de peças.',
        debugging_steps: [
          'Verificar se o part_number existe no catálogo',
          'Cadastrar peça antes de importar movimento',
          'Usar modo de importação com auto-cadastro',
        ],
        suggested_action: 'fallback',
      });

      const dbError = new AgentCoreError(
        'Erro de integridade no banco',
        {
          status: 422,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(dbError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('import.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(result.current.error?.debug_analysis?.debugging_steps).toBeDefined();
      expect(result.current.error?.debug_analysis?.debugging_steps.length).toBe(3);
      expect(result.current.error?.debug_analysis?.suggested_action).toBe('fallback');
    });

    /**
     * Scenario 7: Gemini API failure (rate limit)
     * Expected: Fallback response with llm_powered=false
     */
    it('Scenario 7: Gemini failure - should fallback with llm_powered=false', async () => {
      // Arrange - When Gemini fails, Debug Agent returns rule-based analysis
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'LLMError',
        technical_explanation: 'Limite de taxa da API Gemini excedido. ' +
          'Análise baseada em regras foi utilizada.',
        llm_powered: false, // Fallback mode
        suggested_action: 'retry',
        root_causes: [
          {
            cause: 'Rate limit excedido na API Gemini',
            confidence: 1.0,
            source: 'inference', // Rule-based, not memory/docs
            evidence: ['HTTP 429 recebido'],
          },
        ],
      });

      const llmError = new AgentCoreError(
        'Serviço de IA temporariamente indisponível',
        {
          status: 429,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(llmError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('test.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert - Should indicate fallback mode
      expect(result.current.error?.debug_analysis?.llm_powered).toBe(false);
      expect(result.current.error?.debug_analysis?.error_type).toBe('LLMError');
    });
  });

  // ===========================================================================
  // NEXO Flow Error Handling
  // ===========================================================================

  describe('NEXO Flow Error Handling', () => {
    it('should extract debug_analysis from NEXO analysis errors', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis({
        error_type: 'AnalysisError',
        technical_explanation: 'Falha na análise inteligente do arquivo.',
        suggested_action: 'fallback',
      });

      const nexoError = new AgentCoreError(
        'Falha na análise NEXO',
        {
          status: 500,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(nexoAnalyzeFile).mockRejectedValue(nexoError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadWithNexoAnalysis(
            createMockFile('test.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(result.current.error).not.toBeNull();
      expect(result.current.error?.debug_analysis).toBeDefined();
      expect(result.current.error?.debug_analysis?.error_type).toBe('AnalysisError');
    });
  });

  // ===========================================================================
  // Progress State During Errors
  // ===========================================================================

  describe('Progress State on Error', () => {
    it('should set progress to error stage with message', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis();
      const testError = new AgentCoreError(
        'Teste de progresso',
        {
          status: 500,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(testError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('test.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Assert
      expect(result.current.progress.stage).toBe('error');
      expect(result.current.progress.percent).toBe(0);
      expect(result.current.progress.message).toBe('Teste de progresso');
    });
  });

  // ===========================================================================
  // Clear Preview Reset
  // ===========================================================================

  describe('Error State Reset', () => {
    it('should clear error state on clearPreview', async () => {
      // Arrange
      const mockDebugAnalysis = createMockDebugAnalysis();
      const testError = new AgentCoreError(
        'Error to clear',
        {
          status: 500,
          debug_analysis: mockDebugAnalysis,
        }
      );

      vi.mocked(getNFUploadUrl).mockResolvedValue(createMockUploadUrlResponse());
      vi.mocked(invokeSmartImport).mockRejectedValue(testError);

      const { result } = renderHook(() => useSmartImporter(), {
        wrapper: createWrapper(),
      });

      // Act - First trigger error
      await act(async () => {
        try {
          await result.current.uploadAndProcess(
            createMockFile('test.csv', 'text/csv'),
            null,
            null
          );
        } catch {
          // Expected
        }
      });

      // Verify error exists
      expect(result.current.error).not.toBeNull();

      // Act - Clear preview
      act(() => {
        result.current.clearPreview();
      });

      // Assert - Error should be cleared
      expect(result.current.error).toBeNull();
      expect(result.current.progress.stage).toBe('idle');
    });
  });
});
