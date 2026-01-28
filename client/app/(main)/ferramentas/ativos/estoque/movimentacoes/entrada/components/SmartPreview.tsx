'use client';

// =============================================================================
// SmartPreview - Preview Router Component
// =============================================================================
// Routes to the appropriate preview component based on source_type.
// This is the entry point for displaying smart import results.
//
// FLOW: Preview Confirm → Confirmation Modal → NEXO AI Analysis → Final Confirm → DB Commit
// =============================================================================

import { useState } from 'react';
import type { SmartImportPreview, SmartSourceType } from '@/lib/ativos/smartImportTypes';
import {
  isNFImportResult,
  isSpreadsheetImportResult,
  isTextImportResult,
} from '@/lib/ativos/smartImportTypes';
import { NFPreview } from './previews/NFPreview';
import { SpreadsheetPreview } from './previews/SpreadsheetPreview';
import { TextPreview } from './previews/TextPreview';
import { SmartImportConfirmationModal } from '@/components/ferramentas/ativos/estoque/SmartImportConfirmationModal';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { AlertTriangle, FileQuestion, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getFileTypeLabel } from '@/lib/ativos/smartImportTypes';

// =============================================================================
// Types
// =============================================================================

interface SmartPreviewProps {
  preview: SmartImportPreview;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
}

// =============================================================================
// Component
// =============================================================================

export function SmartPreview({
  preview,
  onConfirm,
  onCancel,
}: SmartPreviewProps) {
  // Modal state - shows Apple TV frosted glass confirmation before DB commit
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);

  // Pre-confirm: Opens confirmation modal instead of directly committing
  // The modal will fetch NEXO AI observations and require explicit user confirmation
  const handlePreConfirm = async () => {
    setShowConfirmModal(true);
  };

  // Final confirm: Called when user confirms in the modal
  // This actually commits the assets to DynamoDB
  const handleFinalConfirm = async () => {
    setIsConfirming(true);
    try {
      await onConfirm();
    } finally {
      setIsConfirming(false);
    }
  };

  // Render the appropriate preview component based on source_type
  // All previews now trigger handlePreConfirm which opens the modal
  const renderPreview = () => {
    // Handle error responses gracefully - show error instead of crashing
    // Backend may return { success: false, error: "..." } when processing fails
    if (!preview.success && 'error' in preview) {
      const errorPreview = preview as SmartImportPreview & {
        error?: string;
        message?: string;
        detected_file_type?: string;
        filename?: string;
      };
      return (
        <ErrorPreview
          error={errorPreview.error || errorPreview.message || 'Erro desconhecido'}
          fileType={errorPreview.detected_file_type}
          filename={errorPreview.filename}
          onCancel={onCancel}
        />
      );
    }

    if (isNFImportResult(preview)) {
      return (
        <NFPreview
          preview={preview}
          onConfirm={handlePreConfirm}
          onCancel={onCancel}
          isConfirming={isConfirming}
        />
      );
    }

    if (isSpreadsheetImportResult(preview)) {
      return (
        <SpreadsheetPreview
          preview={preview}
          onConfirm={handlePreConfirm}
          onCancel={onCancel}
          isConfirming={isConfirming}
        />
      );
    }

    if (isTextImportResult(preview)) {
      return (
        <TextPreview
          preview={preview}
          onConfirm={handlePreConfirm}
          onCancel={onCancel}
          isConfirming={isConfirming}
        />
      );
    }

    // Fallback for unknown preview types (this shouldn't happen with proper typing)
    const unknownPreview = preview as SmartImportPreview;
    return (
      <UnknownPreview
        sourceType={unknownPreview.source_type}
        onCancel={onCancel}
      />
    );
  };

  return (
    <>
      {/* Preview Component (NF, Spreadsheet, Text, or Unknown) */}
      {renderPreview()}

      {/* Apple TV Frosted Glass Confirmation Modal */}
      {/* Shows import summary and NEXO AI observations before final DB commit */}
      <SmartImportConfirmationModal
        open={showConfirmModal}
        onOpenChange={setShowConfirmModal}
        preview={preview}
        onConfirm={handleFinalConfirm}
        isConfirming={isConfirming}
      />
    </>
  );
}

// =============================================================================
// Fallback Component
// =============================================================================

interface UnknownPreviewProps {
  sourceType: SmartSourceType;
  onCancel: () => void;
}

function UnknownPreview({ sourceType, onCancel }: UnknownPreviewProps) {
  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <FileQuestion className="w-4 h-4 text-yellow-400" />
          <GlassCardTitle>Preview Nao Disponivel</GlassCardTitle>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="text-center py-8">
          <AlertTriangle className="w-12 h-12 text-yellow-400 mx-auto mb-4" />
          <p className="text-sm text-text-primary mb-2">
            Tipo de preview desconhecido
          </p>
          <p className="text-xs text-text-muted mb-6">
            O tipo de fonte &quot;{sourceType}&quot; nao possui um preview implementado.
          </p>
          <Button variant="outline" onClick={onCancel}>
            Voltar
          </Button>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}

// =============================================================================
// Error Preview Component
// =============================================================================

interface ErrorPreviewProps {
  error: string;
  fileType?: string;
  filename?: string;
  onCancel: () => void;
}

/**
 * Displays backend processing errors in a user-friendly format.
 * Shows error message, file info, and allows user to try again.
 */
function ErrorPreview({ error, fileType, filename, onCancel }: ErrorPreviewProps) {
  // Get human-friendly file type label
  const fileTypeLabel = fileType
    ? getFileTypeLabel(fileType as 'xlsx' | 'csv' | 'xml' | 'pdf' | 'image' | 'txt' | 'unknown')
    : 'Arquivo';

  return (
    <GlassCard>
      <GlassCardHeader>
        <div className="flex items-center gap-2">
          <XCircle className="w-4 h-4 text-red-400" />
          <GlassCardTitle>Erro ao Processar Arquivo</GlassCardTitle>
        </div>
      </GlassCardHeader>

      <GlassCardContent>
        <div className="text-center py-8">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />

          {filename && (
            <p className="text-sm text-text-primary mb-2 font-medium">
              {filename}
            </p>
          )}

          <p className="text-xs text-text-muted mb-4">
            {fileTypeLabel}
          </p>

          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6 max-w-md mx-auto">
            <p className="text-sm text-red-400">
              {error}
            </p>
          </div>

          <p className="text-xs text-text-muted mb-6">
            Por favor, tente novamente ou entre em contato com o suporte.
          </p>

          <Button variant="outline" onClick={onCancel}>
            Voltar
          </Button>
        </div>
      </GlassCardContent>
    </GlassCard>
  );
}
