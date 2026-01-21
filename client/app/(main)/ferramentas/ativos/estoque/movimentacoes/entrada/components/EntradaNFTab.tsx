'use client';

// =============================================================================
// EntradaNFTab - NF Upload Tab Component
// =============================================================================
// Handles NF (Nota Fiscal Eletronica) file upload and processing.
// Supports XML and PDF formats.
// =============================================================================

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  FileUp,
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Package,
  MapPin,
  Briefcase,
  Clock,
  FolderPlus,
} from 'lucide-react';
import type {
  NFExtraction,
  NFItemMapping,
  ConfidenceScore,
  SGAProject,
  SGALocation,
} from '@/lib/ativos/types';

// Type aliases for cleaner code
type Project = SGAProject;
type Location = SGALocation;

// =============================================================================
// Types
// =============================================================================

interface EntradaNFTabProps {
  // Upload state from useNFReader
  isUploading: boolean;
  uploadProgress: number;
  uploadError: string | null;

  // Extraction state
  extraction: NFExtraction | null;
  confidenceScore: ConfidenceScore | null;
  entryId: string | null;
  requiresReview: boolean;
  requiresProject: boolean;

  // Master data
  projects: Project[];
  locations: Location[];

  // Actions
  onUpload: (file: File, projectId: string | null, locationId: string) => Promise<void>;
  onConfirm: () => Promise<void>;
  onClear: () => void;
  onAssignProject: (entryId: string) => void;

  // Mappings
  mappings: NFItemMapping[];
  updateMapping: (index: number, mapping: Partial<NFItemMapping>) => void;
}

// =============================================================================
// Component
// =============================================================================

export function EntradaNFTab({
  isUploading,
  uploadProgress,
  uploadError,
  extraction,
  confidenceScore,
  entryId,
  requiresReview,
  requiresProject,
  projects,
  locations,
  onUpload,
  onConfirm,
  onClear,
  onAssignProject,
}: EntradaNFTabProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('');

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  // Handle upload
  const handleUpload = async () => {
    if (!selectedFile || !selectedLocation) return;

    try {
      await onUpload(selectedFile, selectedProject || null, selectedLocation);
    } catch {
      // Error is handled by the hook
    }
  };

  // Handle confirm
  const handleConfirm = async () => {
    try {
      await onConfirm();
      setSelectedFile(null);
      setSelectedProject('');
      setSelectedLocation('');
    } catch {
      // Error is handled by the hook
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      {!extraction && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center gap-2">
              <FileUp className="w-4 h-4 text-green-400" />
              <GlassCardTitle>Upload de NF</GlassCardTitle>
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-6">
              {/* Project and Location Selection */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Briefcase className="w-4 h-4 inline mr-2" />
                    Projeto <span className="text-text-muted font-normal">(opcional)</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={selectedProject}
                    onChange={(e) => setSelectedProject(e.target.value)}
                  >
                    <option value="">Sem projeto (atribuir depois)...</option>
                    {projects.filter(p => p.is_active).map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.code} - {project.name}
                      </option>
                    ))}
                  </select>
                  {!selectedProject && (
                    <p className="text-xs text-orange-400 mt-1">
                      <Clock className="w-3 h-3 inline mr-1" />
                      Entrada ficara aguardando atribuicao de projeto
                    </p>
                  )}
                </div>

                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <MapPin className="w-4 h-4 inline mr-2" />
                    Local de Destino
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={selectedLocation}
                    onChange={(e) => setSelectedLocation(e.target.value)}
                  >
                    <option value="">Selecione o local...</option>
                    {locations.filter(l => l.is_active && l.type === 'WAREHOUSE').map((location) => (
                      <option key={location.id} value={location.id}>
                        {location.code} - {location.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* File Upload Area */}
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-blue-mid/50 transition-colors">
                <input
                  type="file"
                  accept=".xml,.pdf"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="nf-upload"
                  disabled={isUploading}
                />
                <label htmlFor="nf-upload" className="cursor-pointer">
                  <Upload className="w-12 h-12 text-text-muted mx-auto mb-4" />
                  <p className="text-sm font-medium text-text-primary mb-1">
                    {selectedFile ? selectedFile.name : 'Clique para selecionar ou arraste o arquivo'}
                  </p>
                  <p className="text-xs text-text-muted">
                    Formatos aceitos: XML ou PDF
                  </p>
                </label>
              </div>

              {/* Upload Progress */}
              {isUploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-muted">Processando NF...</span>
                    <span className="text-text-primary">{uploadProgress}%</span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-blue-mid"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Error */}
              {uploadError && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <p className="text-sm text-red-400">{uploadError}</p>
                </div>
              )}

              {/* Upload Button */}
              <Button
                className="w-full"
                disabled={!selectedFile || !selectedLocation || isUploading}
                onClick={handleUpload}
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Processando...
                  </>
                ) : (
                  <>
                    <FileUp className="w-4 h-4 mr-2" />
                    Processar NF
                  </>
                )}
              </Button>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Extraction Result */}
      {extraction && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center justify-between w-full">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-light" />
                <GlassCardTitle>Dados Extraidos</GlassCardTitle>
              </div>
              {confidenceScore && (
                <Badge className={
                  confidenceScore.risk_level === 'low' ? 'bg-green-500/20 text-green-400' :
                  confidenceScore.risk_level === 'medium' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }>
                  Confianca: {Math.round(confidenceScore.overall * 100)}%
                </Badge>
              )}
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-6">
              {/* NF Info */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-white/5 rounded-lg">
                <div>
                  <p className="text-xs text-text-muted">Numero NF</p>
                  <p className="text-sm font-medium text-text-primary">
                    {extraction.nf_number}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Serie</p>
                  <p className="text-sm font-medium text-text-primary">
                    {extraction.nf_series}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Fornecedor</p>
                  <p className="text-sm font-medium text-text-primary">
                    {extraction.supplier_name}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-text-muted">Data Emissao</p>
                  <p className="text-sm font-medium text-text-primary">
                    {new Date(extraction.issue_date).toLocaleDateString('pt-BR')}
                  </p>
                </div>
              </div>

              {/* Items */}
              <div>
                <h4 className="text-sm font-medium text-text-primary mb-3">
                  Itens ({extraction.items.length})
                </h4>
                <div className="space-y-2">
                  {extraction.items.map((item, index) => (
                    <div key={index} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                      <Package className="w-5 h-5 text-blue-light" />
                      <div className="flex-1">
                        <p className="text-sm text-text-primary">{item.description}</p>
                        <p className="text-xs text-text-muted">
                          Codigo: {item.product_code} - NCM: {item.ncm_code || '-'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-text-primary">
                          Qtd: {item.quantity} {item.unit_of_measure}
                        </p>
                        <p className="text-xs text-text-muted">
                          R$ {item.unit_value.toFixed(2)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Project Gate Warning */}
              {requiresProject && (
                <div className="flex items-start gap-3 p-4 bg-orange-500/20 border border-orange-500/30 rounded-lg">
                  <FolderPlus className="w-5 h-5 text-orange-400 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-orange-400">
                      Aguardando Atribuicao de Projeto
                    </p>
                    <p className="text-xs text-orange-400/80 mt-1">
                      Esta entrada foi criada sem projeto. Atribua um projeto para continuar.
                    </p>
                    <Button
                      size="sm"
                      className="mt-3 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400"
                      onClick={() => entryId && onAssignProject(entryId)}
                    >
                      <FolderPlus className="w-4 h-4 mr-2" />
                      Atribuir Projeto
                    </Button>
                  </div>
                </div>
              )}

              {/* Review Warning */}
              {requiresReview && !requiresProject && (
                <div className="flex items-start gap-3 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-yellow-400">
                      Revisao Necessaria
                    </p>
                    <p className="text-xs text-yellow-400/80 mt-1">
                      Alguns itens precisam de confirmacao manual antes do registro.
                    </p>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex gap-3">
                <Button variant="outline" onClick={onClear} className="flex-1">
                  Cancelar
                </Button>
                <Button
                  onClick={handleConfirm}
                  className="flex-1"
                  disabled={requiresProject}
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  {requiresProject ? 'Atribua um Projeto' : 'Confirmar Entrada'}
                </Button>
              </div>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}
    </div>
  );
}
