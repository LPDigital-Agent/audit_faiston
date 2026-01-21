'use client';

/**
 * KBCitationCard - Knowledge Base Citation Display Component
 *
 * Displays a citation from the equipment documentation Knowledge Base.
 * Shows document metadata, relevance score, and provides download links.
 *
 * Used in NexoCopilot to show sources for AI answers about equipment.
 */

import { FileText, Download, ExternalLink, Sparkles } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { KBCitation, EquipmentDocumentType } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface KBCitationCardProps {
  citation: KBCitation;
  index: number;
  onDownload?: (s3_uri: string) => void;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Get display label for document type.
 */
function getDocumentTypeLabel(docType: EquipmentDocumentType | undefined): string {
  const labels: Record<EquipmentDocumentType, string> = {
    manual: 'Manual',
    datasheet: 'Datasheet',
    spec: 'Especificações',
    guide: 'Guia Rápido',
    firmware: 'Firmware',
    driver: 'Driver',
    unknown: 'Documento',
  };
  return labels[docType ?? 'unknown'];
}

/**
 * Get color scheme for document type badge.
 */
function getDocumentTypeBadgeClass(docType: EquipmentDocumentType | undefined): string {
  const colorMap: Record<EquipmentDocumentType, string> = {
    manual: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    datasheet: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    spec: 'bg-green-500/20 text-green-300 border-green-500/30',
    guide: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    firmware: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    driver: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    unknown: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  };
  return colorMap[docType ?? 'unknown'];
}

/**
 * Get relevance indicator based on score.
 */
function getRelevanceIndicator(score: number): { label: string; color: string } {
  if (score >= 0.8) {
    return { label: 'Alta relevância', color: 'text-green-400' };
  } else if (score >= 0.5) {
    return { label: 'Relevância média', color: 'text-yellow-400' };
  } else {
    return { label: 'Baixa relevância', color: 'text-gray-400' };
  }
}

/**
 * Truncate text to specified length.
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}

// =============================================================================
// Component
// =============================================================================

export function KBCitationCard({ citation, index, onDownload }: KBCitationCardProps) {
  const relevance = getRelevanceIndicator(citation.score);
  const docTypeLabel = getDocumentTypeLabel(citation.document_type);
  const badgeClass = getDocumentTypeBadgeClass(citation.document_type);

  const handleDownload = () => {
    if (citation.download_url) {
      window.open(citation.download_url, '_blank', 'noopener,noreferrer');
    } else if (onDownload) {
      onDownload(citation.s3_uri);
    }
  };

  return (
    <Card className="bg-[var(--faiston-bg-secondary)]/50 border-[var(--faiston-border)] hover:border-[var(--faiston-magenta-mid)]/50 transition-all duration-200">
      <CardContent className="p-3">
        {/* Header Row */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            {/* Index Badge */}
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[var(--faiston-magenta-dark)]/30 text-[var(--faiston-magenta-light)] text-xs flex items-center justify-center font-medium">
              {index + 1}
            </span>

            {/* Document Icon */}
            <FileText className="h-4 w-4 text-[var(--faiston-blue-light)] flex-shrink-0" />

            {/* Title */}
            <span className="text-sm font-medium text-white truncate">
              {citation.title || docTypeLabel}
            </span>
          </div>

          {/* Relevance Score */}
          <div className="flex items-center gap-1 flex-shrink-0">
            <Sparkles className={`h-3 w-3 ${relevance.color}`} />
            <span className={`text-xs ${relevance.color}`}>
              {Math.round(citation.score * 100)}%
            </span>
          </div>
        </div>

        {/* Metadata Row */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {/* Document Type Badge */}
          <Badge variant="outline" className={`text-xs ${badgeClass}`}>
            {docTypeLabel}
          </Badge>

          {/* Part Number if available */}
          {citation.part_number && (
            <Badge variant="outline" className="text-xs bg-[var(--faiston-bg-primary)]/50 text-gray-300 border-gray-600">
              PN: {citation.part_number}
            </Badge>
          )}
        </div>

        {/* Excerpt */}
        {citation.excerpt && (
          <p className="text-xs text-gray-400 leading-relaxed mb-3">
            {truncateText(citation.excerpt, 200)}
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-2">
          {(citation.download_url || onDownload) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDownload}
              className="h-7 text-xs text-[var(--faiston-blue-light)] hover:text-[var(--faiston-cyan)] hover:bg-[var(--faiston-blue-dark)]/20"
            >
              <Download className="h-3 w-3 mr-1" />
              Baixar
            </Button>
          )}

          {citation.s3_uri && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                // Could open a document viewer modal in the future
                console.log('View document:', citation.s3_uri);
              }}
              className="h-7 text-xs text-gray-400 hover:text-white hover:bg-[var(--faiston-bg-secondary)]"
            >
              <ExternalLink className="h-3 w-3 mr-1" />
              Ver
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Citations List Component
// =============================================================================

interface KBCitationsListProps {
  citations: KBCitation[];
  onDownload?: (s3_uri: string) => void;
  maxVisible?: number;
}

/**
 * KBCitationsList - List of Knowledge Base citations
 *
 * Shows collapsible list of citations from KB query results.
 */
export function KBCitationsList({
  citations,
  onDownload,
  maxVisible = 3,
}: KBCitationsListProps) {
  if (!citations || citations.length === 0) {
    return null;
  }

  const visibleCitations = citations.slice(0, maxVisible);
  const hasMore = citations.length > maxVisible;

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <FileText className="h-3.5 w-3.5" />
        <span>Fontes ({citations.length})</span>
      </div>

      {/* Citations */}
      <div className="space-y-2">
        {visibleCitations.map((citation, index) => (
          <KBCitationCard
            key={citation.document_id || index}
            citation={citation}
            index={index}
            onDownload={onDownload}
          />
        ))}
      </div>

      {/* Show more indicator */}
      {hasMore && (
        <p className="text-xs text-gray-500 text-center">
          +{citations.length - maxVisible} mais fontes
        </p>
      )}
    </div>
  );
}

export default KBCitationCard;
