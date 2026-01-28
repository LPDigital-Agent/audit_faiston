'use client';

// =============================================================================
// EntradaSAPTab - SAP Export Import Tab Component
// =============================================================================
// Handles CSV/XLSX bulk import from SAP or other ERP systems.
// Creates full asset records with all metadata (serial, RFID, technician, etc).
// =============================================================================

import { useState, useCallback } from 'react';
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
  FileSpreadsheet,
  Upload,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Package,
  MapPin,
  Briefcase,
  Database,
  FileDown,
  Check,
  X,
  Users,
  Hash,
} from 'lucide-react';
import type { SGAProject, SGALocation } from '@/lib/ativos/types';
import type { SAPImportPreview } from '@/hooks/ativos';

// Type aliases for cleaner code
type Project = SGAProject;
type Location = SGALocation;

interface EntradaSAPTabProps {
  // Upload state
  isProcessing: boolean;
  progress: number;
  error: string | null;

  // Preview state
  preview: SAPImportPreview | null;

  // Master data
  projects: Project[];
  locations: Location[];

  // Actions
  onPreview: (file: File, projectId?: string, locationId?: string) => Promise<void>;
  onExecute: () => Promise<void>;
  onClear: () => void;
}

// =============================================================================
// SAP Column Mapping Display
// =============================================================================

const SAP_COLUMN_LABELS: Record<string, string> = {
  source_system: 'Sistema Origem',
  sap_material_code: 'Codigo Material SAP',
  part_number: 'Part Number',
  asset_type: 'Tipo Ativo',
  manufacturer: 'Fabricante',
  serial_number: 'Serial',
  rfid: 'RFID',
  quantity: 'Quantidade',
  uom: 'Unidade',
  project_id: 'ID Projeto',
  project_name: 'Nome Projeto',
  client_cnpj: 'CNPJ Cliente',
  ownership: 'Propriedade',
  sap_depot_code: 'Codigo Deposito',
  sap_depot_name: 'Nome Deposito',
  site: 'Site',
  location_type: 'Tipo Local',
  physical_address: 'Endereco',
  technician_id: 'ID Tecnico',
  technician_name: 'Nome Tecnico',
  technician_city: 'Cidade Tecnico',
  technician_state: 'Estado Tecnico',
  status: 'Status',
  nf_number: 'Numero NF',
  nf_date: 'Data NF',
  sap_document: 'Documento SAP',
  sap_posting_date: 'Data Lancamento',
  tiflux_ticket_id: 'Chamado Tiflux',
  last_inventory_count_date: 'Ultimo Inventario',
  notes: 'Observacoes',
};

// =============================================================================
// Component
// =============================================================================

export function EntradaSAPTab({
  isProcessing,
  progress,
  error,
  preview,
  projects,
  locations,
  onPreview,
  onExecute,
  onClear,
}: EntradaSAPTabProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('');

  // Handle file selection
  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  }, []);

  // Handle drag and drop
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && (file.name.endsWith('.csv') || file.name.endsWith('.xlsx'))) {
      setSelectedFile(file);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  }, []);

  // Handle preview
  const handlePreview = async () => {
    if (!selectedFile) return;

    try {
      await onPreview(selectedFile, selectedProject || undefined, selectedLocation || undefined);
    } catch {
      // Error handled by hook
    }
  };

  // Handle execute
  const handleExecute = async () => {
    try {
      await onExecute();
      setSelectedFile(null);
      setSelectedProject('');
      setSelectedLocation('');
    } catch {
      // Error handled by hook
    }
  };

  // Handle clear
  const handleClear = () => {
    setSelectedFile(null);
    onClear();
  };

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-cyan-500/10 border border-cyan-500/20 rounded-lg">
        <Database className="w-5 h-5 text-cyan-400 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-cyan-400">
            Importacao SAP/ERP com Asset Completo
          </p>
          <p className="text-xs text-cyan-400/80 mt-1">
            Importe arquivos CSV ou XLSX exportados do SAP ou outro ERP. O sistema criara
            registros de assets completos com serial, RFID, tecnico responsavel e status.
          </p>
        </div>
      </div>

      {/* Upload Section */}
      {!preview && (
        <GlassCard>
          <GlassCardHeader>
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
              <GlassCardTitle>Upload de Arquivo SAP</GlassCardTitle>
            </div>
          </GlassCardHeader>

          <GlassCardContent>
            <div className="space-y-6">
              {/* Project and Location Selection (Optional for SAP) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <Briefcase className="w-4 h-4 inline mr-2" />
                    Projeto Padrao <span className="text-text-muted font-normal">(opcional)</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={selectedProject}
                    onChange={(e) => setSelectedProject(e.target.value)}
                  >
                    <option value="">Usar projeto do arquivo...</option>
                    {projects.filter(p => p.is_active).map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.code} - {project.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-text-muted mt-1">
                    Se nao selecionado, usara a coluna project_id do arquivo
                  </p>
                </div>

                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    <MapPin className="w-4 h-4 inline mr-2" />
                    Local Padrao <span className="text-text-muted font-normal">(opcional)</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                    value={selectedLocation}
                    onChange={(e) => setSelectedLocation(e.target.value)}
                  >
                    <option value="">Usar local do arquivo...</option>
                    {locations.filter(l => l.is_active).map((location) => (
                      <option key={location.id} value={location.id}>
                        {location.code} - {location.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-text-muted mt-1">
                    Se nao selecionado, usara a coluna sap_depot_code
                  </p>
                </div>
              </div>

              {/* File Upload Area */}
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  selectedFile
                    ? 'border-cyan-500/50 bg-cyan-500/5'
                    : 'border-border hover:border-cyan-500/50'
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
              >
                <input
                  type="file"
                  accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="sap-upload"
                  disabled={isProcessing}
                />

                {selectedFile ? (
                  <div className="space-y-4">
                    <FileSpreadsheet className="w-12 h-12 text-cyan-400 mx-auto" />
                    <div>
                      <p className="text-sm font-medium text-text-primary">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-text-muted">
                        {(selectedFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedFile(null)}
                    >
                      Trocar arquivo
                    </Button>
                  </div>
                ) : (
                  <label htmlFor="sap-upload" className="cursor-pointer">
                    <Upload className="w-12 h-12 text-text-muted mx-auto mb-4" />
                    <p className="text-sm font-medium text-text-primary mb-1">
                      Clique para selecionar ou arraste o arquivo
                    </p>
                    <p className="text-xs text-text-muted">
                      Formatos aceitos: CSV ou XLSX (exportacao SAP)
                    </p>
                  </label>
                )}
              </div>

              {/* Processing Progress */}
              {isProcessing && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-muted">
                      <Database className="w-4 h-4 inline mr-2 animate-pulse" />
                      Analisando arquivo...
                    </span>
                    <span className="text-text-primary">{progress}%</span>
                  </div>
                  <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-cyan-600 to-cyan-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}

              {/* Preview Button */}
              <Button
                className="w-full bg-gradient-to-r from-cyan-600 to-cyan-500 hover:opacity-90 text-white"
                disabled={!selectedFile || isProcessing}
                onClick={handlePreview}
              >
                {isProcessing ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Analisando...
                  </>
                ) : (
                  <>
                    <FileDown className="w-4 h-4 mr-2" />
                    Visualizar Importacao
                  </>
                )}
              </Button>
            </div>
          </GlassCardContent>
        </GlassCard>
      )}

      {/* Preview Section */}
      {preview && (
        <div className="space-y-6">
          {/* Stats Card */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-cyan-400" />
                  <GlassCardTitle>Preview: {preview.filename}</GlassCardTitle>
                </div>
                {preview.is_sap_format && (
                  <Badge className="bg-cyan-500/20 text-cyan-400">
                    Formato SAP Detectado
                  </Badge>
                )}
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-white/5 rounded-lg text-center">
                  <p className="text-2xl font-bold text-text-primary">
                    {preview.total_rows}
                  </p>
                  <p className="text-xs text-text-muted">Total de Linhas</p>
                </div>
                <div className="p-4 bg-green-500/10 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-400">
                    {preview.matched_rows}
                  </p>
                  <p className="text-xs text-text-muted">PNs Mapeados</p>
                </div>
                <div className="p-4 bg-orange-500/10 rounded-lg text-center">
                  <p className="text-2xl font-bold text-orange-400">
                    {preview.unmatched_rows}
                  </p>
                  <p className="text-xs text-text-muted">Nao Mapeados</p>
                </div>
                <div className="p-4 bg-blue-500/10 rounded-lg text-center">
                  <p className="text-2xl font-bold text-blue-400">
                    {preview.assets_to_create}
                  </p>
                  <p className="text-xs text-text-muted">Assets a Criar</p>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Columns Detected */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Hash className="w-4 h-4 text-text-muted" />
                <GlassCardTitle>Colunas Detectadas ({preview.columns_detected.length})</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="flex flex-wrap gap-2">
                {preview.columns_detected.map((col) => (
                  <Badge
                    key={col}
                    variant="outline"
                    className={SAP_COLUMN_LABELS[col] ? 'border-green-500/50 text-green-400' : ''}
                  >
                    {SAP_COLUMN_LABELS[col] ? (
                      <Check className="w-3 h-3 mr-1" />
                    ) : (
                      <X className="w-3 h-3 mr-1" />
                    )}
                    {SAP_COLUMN_LABELS[col] || col}
                  </Badge>
                ))}
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Detected Projects & Locations */}
          {(preview.projects_detected.length > 0 || preview.locations_detected.length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {preview.projects_detected.length > 0 && (
                <GlassCard>
                  <GlassCardHeader>
                    <div className="flex items-center gap-2">
                      <Briefcase className="w-4 h-4 text-text-muted" />
                      <GlassCardTitle>Projetos no Arquivo</GlassCardTitle>
                    </div>
                  </GlassCardHeader>
                  <GlassCardContent>
                    <div className="flex flex-wrap gap-2">
                      {preview.projects_detected.map((proj) => (
                        <Badge key={proj} variant="outline">
                          {proj}
                        </Badge>
                      ))}
                    </div>
                  </GlassCardContent>
                </GlassCard>
              )}

              {preview.locations_detected.length > 0 && (
                <GlassCard>
                  <GlassCardHeader>
                    <div className="flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-text-muted" />
                      <GlassCardTitle>Locais no Arquivo</GlassCardTitle>
                    </div>
                  </GlassCardHeader>
                  <GlassCardContent>
                    <div className="flex flex-wrap gap-2">
                      {preview.locations_detected.slice(0, 10).map((loc) => (
                        <Badge key={loc} variant="outline">
                          {loc}
                        </Badge>
                      ))}
                      {preview.locations_detected.length > 10 && (
                        <Badge variant="outline">
                          +{preview.locations_detected.length - 10} mais
                        </Badge>
                      )}
                    </div>
                  </GlassCardContent>
                </GlassCard>
              )}
            </div>
          )}

          {/* Sample Data */}
          {preview.sample_data.length > 0 && (
            <GlassCard>
              <GlassCardHeader>
                <div className="flex items-center gap-2">
                  <Package className="w-4 h-4 text-text-muted" />
                  <GlassCardTitle>Amostra de Dados (5 primeiros)</GlassCardTitle>
                </div>
              </GlassCardHeader>

              <GlassCardContent>
                <div className="overflow-x-auto">
                  <div className="space-y-2">
                    {preview.sample_data.slice(0, 5).map((row, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-4 p-3 bg-white/5 rounded-lg"
                      >
                        <Package className="w-5 h-5 text-cyan-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-text-primary truncate">
                            {row.part_number || row.description || 'N/A'}
                          </p>
                          <p className="text-xs text-text-muted">
                            Serial: {row.serial_number || '-'} |
                            Projeto: {row.project_name || row.project_id || '-'} |
                            Status: {row.status || '-'}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-sm font-medium text-text-primary">
                            Qtd: {row.quantity || 1}
                          </p>
                          {row.technician_name && (
                            <p className="text-xs text-text-muted">
                              <Users className="w-3 h-3 inline mr-1" />
                              {row.technician_name}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </GlassCardContent>
            </GlassCard>
          )}

          {/* Warning if low match rate */}
          {preview.match_rate < 80 && (
            <div className="flex items-start gap-3 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-yellow-400">
                  Taxa de Mapeamento Baixa ({Math.round(preview.match_rate)}%)
                </p>
                <p className="text-xs text-yellow-400/80 mt-1">
                  Alguns Part Numbers nao foram encontrados no cadastro.
                  Eles serao criados automaticamente durante a importacao.
                </p>
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleClear} className="flex-1">
              Cancelar
            </Button>
            <Button
              onClick={handleExecute}
              className="flex-1 bg-gradient-to-r from-cyan-600 to-cyan-500"
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  Importando...
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Executar Importacao ({preview.assets_to_create} assets)
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
