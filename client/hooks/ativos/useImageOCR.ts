// =============================================================================
// useImageOCR Hook - SGA Inventory Module
// =============================================================================
// Image OCR upload and processing via Gemini Vision.
// Handles JPEG/PNG images (scanned NF, mobile photos).
// =============================================================================


import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getNFUploadUrl,
  processImageOCR,
  confirmNFEntry,
  type SGAGetUploadUrlResponse,  // BUG-014: Type for extraction
} from '@/services/sgaAgentcore';
import { extractAgentResponse } from '@/utils/agentcoreResponse';  // BUG-014: A2A response extraction
import type {
  NFExtraction,
  NFItemMapping,
  ConfidenceScore,
  SGAProcessNFUploadResponse,
  SGAConfirmNFEntryResponse,
} from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

export interface UseImageOCRReturn {
  // Processing state
  isProcessing: boolean;
  progress: number;
  error: string | null;

  // Extraction state
  extraction: NFExtraction | null;
  suggestedMappings: NFItemMapping[];
  confidenceScore: ConfidenceScore | null;
  entryId: string | null;
  requiresReview: boolean;
  requiresProject: boolean;

  // Actions
  processImage: (
    file: File,
    projectId: string | null,
    destinationLocationId: string
  ) => Promise<SGAProcessNFUploadResponse>;
  confirmEntry: (
    entryId: string,
    itemMappings: NFItemMapping[],
    notes?: string
  ) => Promise<SGAConfirmNFEntryResponse>;
  clearResult: () => void;

  // Item mapping helpers
  mappings: NFItemMapping[];
  updateMapping: (index: number, mapping: Partial<NFItemMapping>) => void;
}

// =============================================================================
// Hook
// =============================================================================

export function useImageOCR(): UseImageOCRReturn {
  const queryClient = useQueryClient();

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Extraction state
  const [extraction, setExtraction] = useState<NFExtraction | null>(null);
  const [suggestedMappings, setSuggestedMappings] = useState<NFItemMapping[]>([]);
  const [mappings, setMappings] = useState<NFItemMapping[]>([]);
  const [confidenceScore, setConfidenceScore] = useState<ConfidenceScore | null>(null);
  const [entryId, setEntryId] = useState<string | null>(null);
  const [requiresReview, setRequiresReview] = useState(false);
  const [requiresProject, setRequiresProject] = useState(false);

  // Process image with OCR
  const processImage = useCallback(async (
    file: File,
    projectId: string | null,
    destinationLocationId: string
  ): Promise<SGAProcessNFUploadResponse> => {
    setIsProcessing(true);
    setProgress(0);
    setError(null);
    setRequiresProject(false);

    try {
      // 1. Validate file type
      const validTypes = ['image/jpeg', 'image/png', 'image/jpg'];
      if (!validTypes.includes(file.type)) {
        throw new Error('Formato invalido. Use JPEG ou PNG.');
      }

      // 2. Get presigned URL for image upload
      setProgress(10);
      const urlResult = await getNFUploadUrl({
        filename: file.name,
        content_type: file.type,
      });

      // BUG-014: Extract response from A2A wrapped format
      const uploadUrlData = extractAgentResponse<SGAGetUploadUrlResponse>(urlResult.data);

      if (!uploadUrlData?.upload_url || !uploadUrlData?.s3_key) {
        throw new Error('Falha ao obter URL de upload');
      }

      // 3. Upload to S3
      // CRITICAL: Use required_headers from backend - these values are signed into the presigned URL
      setProgress(30);
      const uploadHeaders = uploadUrlData.required_headers || { 'Content-Type': file.type };
      const uploadResponse = await fetch(uploadUrlData.upload_url, {
        method: 'PUT',
        body: file,
        headers: uploadHeaders,
      });

      if (!uploadResponse.ok) {
        throw new Error('Falha no upload da imagem');
      }

      // 4. Process image with OCR (Gemini Vision)
      setProgress(50);
      const processResult = await processImageOCR({
        s3_key: uploadUrlData.s3_key,
        project_id: projectId || '',
        destination_location_id: destinationLocationId,
      });

      setProgress(100);

      // Update state with extraction result
      setExtraction(processResult.data.extraction);
      setSuggestedMappings(processResult.data.suggested_mappings);
      setMappings(processResult.data.suggested_mappings);
      setConfidenceScore(processResult.data.confidence_score);
      setEntryId(processResult.data.entry_id);
      setRequiresReview(processResult.data.requires_review);

      // Check if entry requires project assignment
      const needsProject = (processResult.data as unknown as { requires_project?: boolean }).requires_project ?? false;
      setRequiresProject(needsProject);

      return processResult.data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao processar imagem';
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

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
      clearResult();
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
      queryClient.invalidateQueries({ queryKey: ['sga-pending-nf-entries'] });
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

  // Clear result state
  const clearResult = useCallback(() => {
    setExtraction(null);
    setSuggestedMappings([]);
    setMappings([]);
    setConfidenceScore(null);
    setEntryId(null);
    setRequiresReview(false);
    setRequiresProject(false);
    setError(null);
    setProgress(0);
  }, []);

  // Update mapping
  const updateMapping = useCallback((index: number, mapping: Partial<NFItemMapping>) => {
    setMappings(prev =>
      prev.map((m, i) => (i === index ? { ...m, ...mapping } : m))
    );
  }, []);

  return {
    isProcessing,
    progress,
    error,
    extraction,
    suggestedMappings,
    confidenceScore,
    entryId,
    requiresReview,
    requiresProject,
    processImage,
    confirmEntry,
    clearResult,
    mappings,
    updateMapping,
  };
}

// Re-export types
export type { NFExtraction, NFItemMapping, ConfidenceScore };
