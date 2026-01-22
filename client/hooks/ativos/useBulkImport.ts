// =============================================================================
// useBulkImport Hook - SGA Inventory Module
// =============================================================================
// Hook for bulk importing inventory data from CSV/Excel files.
// Handles file upload, preview, column mapping, and execution.
// =============================================================================

'use client';

import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  previewImport,
  executeImport,
  validatePNMapping,
} from '@/services/sgaAgentcore';
import { safeExtractErrorMessage } from '@/utils/agentcoreResponse';  // BUG-022: Handle double-encoded errors
import type {
  ImportColumnMapping,
  ImportPreviewRow,
  SGAImportPreviewResponse,
  SGAImportExecuteResponse,
  SGAPNMappingValidationResponse,
  SGAPartNumber,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

export interface UseBulkImportReturn {
  // State
  isLoading: boolean;
  isPreviewing: boolean;
  isExecuting: boolean;
  error: string | null;

  // Preview data
  preview: SGAImportPreviewResponse | null;
  columnMappings: ImportColumnMapping[];
  matchedRows: ImportPreviewRow[];
  unmatchedRows: ImportPreviewRow[];

  // PN overrides (manual mappings)
  pnOverrides: Record<number, string>;

  // Actions
  uploadAndPreview: (
    file: File,
    projectId?: string,
    destinationLocationId?: string
  ) => Promise<SGAImportPreviewResponse | null>;
  executeImportAction: () => Promise<SGAImportExecuteResponse | null>;
  updateColumnMapping: (
    index: number,
    targetField: string
  ) => void;
  setPNOverride: (rowNumber: number, pnId: string) => void;
  removePNOverride: (rowNumber: number) => void;
  validateMapping: (
    description: string,
    suggestedPnId?: string
  ) => Promise<SGAPNMappingValidationResponse | null>;
  clearImport: () => void;

  // File info
  filename: string | null;
  fileContent: string | null; // Base64
}

// =============================================================================
// Hook
// =============================================================================

export function useBulkImport(): UseBulkImportReturn {
  const queryClient = useQueryClient();

  // State
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<SGAImportPreviewResponse | null>(null);
  const [columnMappings, setColumnMappings] = useState<ImportColumnMapping[]>([]);
  const [matchedRows, setMatchedRows] = useState<ImportPreviewRow[]>([]);
  const [unmatchedRows, setUnmatchedRows] = useState<ImportPreviewRow[]>([]);
  const [pnOverrides, setPnOverrides] = useState<Record<number, string>>({});
  const [filename, setFilename] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | undefined>();
  const [destinationLocationId, setDestinationLocationId] = useState<string | undefined>();

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: async (params: {
      file_content_base64: string;
      filename: string;
      project_id?: string;
      destination_location_id?: string;
    }) => {
      const result = await previewImport(params);
      return result.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        setPreview(data);
        setColumnMappings(data.column_mappings);
        setMatchedRows(data.matched_rows);
        setUnmatchedRows(data.unmatched_rows);
        setError(null);
      } else {
        // BUG-022 FIX: Handle double-encoded error messages from AgentCore
        setError(safeExtractErrorMessage(data.error) || 'Erro ao processar arquivo');
      }
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Erro ao processar arquivo');
    },
  });

  // Execute mutation
  const executeMutation = useMutation({
    mutationFn: async () => {
      if (!preview || !fileContent || !filename) {
        throw new Error('Nenhum arquivo carregado para importar');
      }

      const result = await executeImport({
        import_id: preview.import_id,
        file_content_base64: fileContent,
        filename: filename,
        column_mappings: columnMappings.map((m) => ({
          file_column: m.file_column,
          target_field: m.target_field,
        })),
        pn_overrides: pnOverrides,
        project_id: projectId,
        destination_location_id: destinationLocationId,
      });

      return result.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        // Invalidate relevant queries
        queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
        queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
        queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
      }
    },
  });

  // Upload and preview file
  const uploadAndPreview = useCallback(
    async (
      file: File,
      pId?: string,
      destLocId?: string
    ): Promise<SGAImportPreviewResponse | null> => {
      setIsLoading(true);
      setError(null);

      try {
        // Read file as base64
        const base64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            const result = reader.result as string;
            // Remove data URL prefix if present
            const base64Data = result.includes(',')
              ? result.split(',')[1]
              : result;
            resolve(base64Data);
          };
          reader.onerror = () => reject(new Error('Erro ao ler arquivo'));
          reader.readAsDataURL(file);
        });

        // Store file info
        setFilename(file.name);
        setFileContent(base64);
        setProjectId(pId);
        setDestinationLocationId(destLocId);

        // Call preview
        const result = await previewMutation.mutateAsync({
          file_content_base64: base64,
          filename: file.name,
          project_id: pId,
          destination_location_id: destLocId,
        });

        return result;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Erro ao processar arquivo';
        setError(message);
        return null;
      } finally {
        setIsLoading(false);
      }
    },
    [previewMutation]
  );

  // Execute import
  const executeImportAction = useCallback(async (): Promise<SGAImportExecuteResponse | null> => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await executeMutation.mutateAsync();

      if (!result.success) {
        // BUG-022 FIX: Handle double-encoded error messages from AgentCore
        setError(safeExtractErrorMessage(result.error) || 'Erro na importação');
      }

      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro na importação';
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [executeMutation]);

  // Update column mapping
  const updateColumnMapping = useCallback(
    (index: number, targetField: string) => {
      setColumnMappings((prev) =>
        prev.map((m, i) =>
          i === index ? { ...m, target_field: targetField } : m
        )
      );
    },
    []
  );

  // Set PN override
  const setPNOverride = useCallback((rowNumber: number, pnId: string) => {
    setPnOverrides((prev) => ({ ...prev, [rowNumber]: pnId }));
  }, []);

  // Remove PN override
  const removePNOverride = useCallback((rowNumber: number) => {
    setPnOverrides((prev) => {
      const next = { ...prev };
      delete next[rowNumber];
      return next;
    });
  }, []);

  // Validate mapping
  const validateMapping = useCallback(
    async (
      description: string,
      suggestedPnId?: string
    ): Promise<SGAPNMappingValidationResponse | null> => {
      try {
        const result = await validatePNMapping({
          description,
          suggested_pn_id: suggestedPnId,
        });
        return result.data;
      } catch (err) {
        return null;
      }
    },
    []
  );

  // Clear import
  const clearImport = useCallback(() => {
    setPreview(null);
    setColumnMappings([]);
    setMatchedRows([]);
    setUnmatchedRows([]);
    setPnOverrides({});
    setFilename(null);
    setFileContent(null);
    setProjectId(undefined);
    setDestinationLocationId(undefined);
    setError(null);
  }, []);

  return {
    isLoading,
    isPreviewing: previewMutation.isPending,
    isExecuting: executeMutation.isPending,
    error,
    preview,
    columnMappings,
    matchedRows,
    unmatchedRows,
    pnOverrides,
    uploadAndPreview,
    executeImportAction,
    updateColumnMapping,
    setPNOverride,
    removePNOverride,
    validateMapping,
    clearImport,
    filename,
    fileContent,
  };
}

// Re-export types
export type {
  ImportColumnMapping,
  ImportPreviewRow,
  SGAImportPreviewResponse,
  SGAImportExecuteResponse,
  SGAPNMappingValidationResponse,
};
