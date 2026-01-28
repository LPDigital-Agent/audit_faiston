// =============================================================================
// useNFReader Hook - SGA Inventory Module
// =============================================================================
// NF (Nota Fiscal Eletronica) upload and processing.
// Handles file upload, extraction, and entry confirmation.
// =============================================================================


import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getNFUploadUrl,
  processNFUpload,
  confirmNFEntry,
  getPendingNFEntries,
  assignProjectToEntry,
  type SGAGetUploadUrlResponse,  // BUG-014: Type for extraction
} from '@/services/sgaAgentcore';
import { extractAgentResponse } from '@/utils/agentcoreResponse';  // BUG-014: A2A response extraction
import type {
  NFExtraction,
  NFItemMapping,
  PendingNFEntry,
  SGAProcessNFUploadResponse,
  SGAConfirmNFEntryResponse,
  ConfidenceScore,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface UseNFReaderReturn {
  // Upload state
  isUploading: boolean;
  uploadProgress: number;
  uploadError: string | null;

  // Extraction state
  extraction: NFExtraction | null;
  suggestedMappings: NFItemMapping[];
  confidenceScore: ConfidenceScore | null;
  entryId: string | null;
  requiresReview: boolean;
  requiresProject: boolean;

  // Pending entries
  pendingEntries: PendingNFEntry[];
  pendingEntriesLoading: boolean;
  refreshPendingEntries: () => void;

  // Actions
  uploadNF: (file: File, projectId: string | null, destinationLocationId: string) => Promise<SGAProcessNFUploadResponse>;
  confirmEntry: (entryId: string, itemMappings: NFItemMapping[], notes?: string) => Promise<SGAConfirmNFEntryResponse>;
  assignProject: (entryId: string, projectId: string) => Promise<void>;
  clearExtraction: () => void;

  // Item mapping helpers
  updateMapping: (index: number, mapping: Partial<NFItemMapping>) => void;
  mappings: NFItemMapping[];
}

// =============================================================================
// Query Keys
// =============================================================================

const PENDING_ENTRIES_KEY = 'sga-pending-nf-entries';

// =============================================================================
// Hook
// =============================================================================

export function useNFReader(): UseNFReaderReturn {
  const queryClient = useQueryClient();

  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Extraction state
  const [extraction, setExtraction] = useState<NFExtraction | null>(null);
  const [suggestedMappings, setSuggestedMappings] = useState<NFItemMapping[]>([]);
  const [mappings, setMappings] = useState<NFItemMapping[]>([]);
  const [confidenceScore, setConfidenceScore] = useState<ConfidenceScore | null>(null);
  const [entryId, setEntryId] = useState<string | null>(null);
  const [requiresReview, setRequiresReview] = useState(false);
  const [requiresProject, setRequiresProject] = useState(false);

  // Fetch pending entries
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
  });

  // Upload NF file (projectId is optional - entries without project go to PENDING_PROJECT)
  const uploadNF = useCallback(async (
    file: File,
    projectId: string | null,
    destinationLocationId: string
  ): Promise<SGAProcessNFUploadResponse> => {
    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setRequiresProject(false);

    try {
      // 1. Get presigned URL
      setUploadProgress(10);
      const fileType = file.name.toLowerCase().endsWith('.xml') ? 'xml' : 'pdf';
      const urlResult = await getNFUploadUrl({
        filename: file.name,
        content_type: file.type || (fileType === 'xml' ? 'application/xml' : 'application/pdf'),
      });

      // BUG-014: Extract response from A2A wrapped format
      const uploadUrlData = extractAgentResponse<SGAGetUploadUrlResponse>(urlResult.data);

      if (!uploadUrlData?.upload_url || !uploadUrlData?.s3_key) {
        throw new Error('Falha ao obter URL de upload');
      }

      // 2. Upload to S3
      // CRITICAL: Use required_headers from backend - these values are signed into the presigned URL
      setUploadProgress(30);
      const defaultContentType = file.type || (fileType === 'xml' ? 'application/xml' : 'application/pdf');
      const uploadHeaders = uploadUrlData.required_headers || { 'Content-Type': defaultContentType };
      const uploadResponse = await fetch(uploadUrlData.upload_url, {
        method: 'PUT',
        body: file,
        headers: uploadHeaders,
      });

      if (!uploadResponse.ok) {
        throw new Error('Falha no upload do arquivo');
      }

      // 3. Process NF (projectId can be empty string or null)
      setUploadProgress(60);
      const processResult = await processNFUpload({
        s3_key: uploadUrlData.s3_key,
        file_type: fileType,
        project_id: projectId || '', // Empty string means no project assigned
        destination_location_id: destinationLocationId,
      });

      setUploadProgress(100);

      // Update state
      setExtraction(processResult.data.extraction);
      setSuggestedMappings(processResult.data.suggested_mappings);
      setMappings(processResult.data.suggested_mappings);
      setConfidenceScore(processResult.data.confidence_score);
      setEntryId(processResult.data.entry_id);
      setRequiresReview(processResult.data.requires_review);

      // Check if entry requires project assignment
      // The backend returns requires_project: true when status is PENDING_PROJECT
      const needsProject = (processResult.data as unknown as { requires_project?: boolean }).requires_project ?? false;
      setRequiresProject(needsProject);

      // Refresh pending entries
      refreshPendingEntries();

      return processResult.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao processar NF';
      setUploadError(message);
      throw error;
    } finally {
      setIsUploading(false);
    }
  }, [refreshPendingEntries]);

  // Confirm entry mutation
  const confirmEntryMutation = useMutation({
    mutationFn: async ({
      entryId,
      itemMappings,
      notes,
    }: {
      entryId: string;
      itemMappings: NFItemMapping[];
      notes?: string;
    }) => {
      const result = await confirmNFEntry({
        entry_id: entryId,
        item_mappings: itemMappings,
        notes,
      });
      return result.data;
    },
    onSuccess: () => {
      // Clear extraction state
      clearExtraction();
      // Refresh pending entries
      refreshPendingEntries();
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
    },
  });

  // Confirm entry wrapper
  const confirmEntry = useCallback(async (
    entryId: string,
    itemMappings: NFItemMapping[],
    notes?: string
  ): Promise<SGAConfirmNFEntryResponse> => {
    return confirmEntryMutation.mutateAsync({ entryId, itemMappings, notes });
  }, [confirmEntryMutation]);

  // Clear extraction state
  const clearExtraction = useCallback(() => {
    setExtraction(null);
    setSuggestedMappings([]);
    setMappings([]);
    setConfidenceScore(null);
    setEntryId(null);
    setRequiresReview(false);
    setRequiresProject(false);
    setUploadError(null);
    setUploadProgress(0);
  }, []);

  // Assign project to an entry in PENDING_PROJECT status
  const assignProject = useCallback(async (entryId: string, projectId: string): Promise<void> => {
    try {
      await assignProjectToEntry(entryId, projectId);
      // Clear the requires project flag if it was for the current entry
      setRequiresProject(false);
      // Refresh pending entries to update status
      refreshPendingEntries();
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro ao atribuir projeto';
      throw new Error(message);
    }
  }, [queryClient, refreshPendingEntries]);

  // Update mapping
  const updateMapping = useCallback((index: number, mapping: Partial<NFItemMapping>) => {
    setMappings(prev =>
      prev.map((m, i) => (i === index ? { ...m, ...mapping } : m))
    );
  }, []);

  return {
    isUploading,
    uploadProgress,
    uploadError,
    extraction,
    suggestedMappings,
    confidenceScore,
    entryId,
    requiresReview,
    requiresProject,
    pendingEntries: pendingEntriesData ?? [],
    pendingEntriesLoading,
    refreshPendingEntries,
    uploadNF,
    confirmEntry,
    assignProject,
    clearExtraction,
    updateMapping,
    mappings,
  };
}

// Re-export types
export type { NFExtraction, NFItemMapping, PendingNFEntry, ConfidenceScore };
