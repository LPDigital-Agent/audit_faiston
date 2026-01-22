// =============================================================================
// useSAPImport Hook - SGA Inventory Module
// =============================================================================
// SAP/ERP CSV/XLSX import with full asset creation.
// Handles 30+ column SAP export format with serial, RFID, technician data.
// =============================================================================

'use client';

import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  previewSAPImport,
  executeSAPImport,
} from '@/services/sgaAgentcore';

// =============================================================================
// Types
// =============================================================================

export interface SAPColumnMapping {
  file_column: string;
  sap_field: string;
  target_field: string;
  confidence: number;
  is_required: boolean;
  sample_values: string[];
}

export interface SAPImportPreviewRow {
  row_number: number;
  part_number: string;
  part_number_id?: string;
  description: string;
  serial_number?: string;
  rfid?: string;
  quantity: number;
  status?: string;
  project_id?: string;
  project_name?: string;
  location_code?: string;
  technician_name?: string;
  match_confidence: number;
  is_matched: boolean;
  warnings: string[];
}

export interface SAPImportPreview {
  import_id: string;
  filename: string;
  file_type: 'csv' | 'xlsx';
  total_rows: number;
  matched_rows: number;
  unmatched_rows: number;
  match_rate: number;
  is_sap_format: boolean;
  columns_detected: string[];
  column_mappings: SAPColumnMapping[];
  sample_data: SAPImportPreviewRow[];
  projects_detected: string[];
  locations_detected: string[];
  assets_to_create: number;
  warnings: string[];
}

export interface SAPImportResult {
  success: boolean;
  import_id: string;
  assets_created: number;
  movements_created: number;
  errors: string[];
  warnings: string[];
}

export interface UseSAPImportReturn {
  // Processing state
  isProcessing: boolean;
  progress: number;
  error: string | null;

  // Preview state
  preview: SAPImportPreview | null;
  columnMappings: SAPColumnMapping[];
  matchedRows: SAPImportPreviewRow[];
  unmatchedRows: SAPImportPreviewRow[];

  // PN overrides
  pnOverrides: Record<number, string>;
  setPNOverride: (rowNumber: number, pnId: string) => void;

  // Actions
  uploadAndPreview: (
    file: File,
    projectId?: string,
    locationId?: string
  ) => Promise<SAPImportPreview>;
  executeImport: () => Promise<SAPImportResult>;
  clearPreview: () => void;

  // Result
  result: SAPImportResult | null;
}

// =============================================================================
// SAP Column Constants
// =============================================================================

export const SAP_EXPECTED_COLUMNS = {
  source_system: ['source_system', 'sistema', 'origem'],
  sap_material_code: ['sap_material_code', 'cod_material_sap', 'material_sap'],
  part_number: ['part_number', 'pn', 'codigo', 'part_num'],
  asset_type: ['asset_type', 'tipo_ativo', 'tipo'],
  manufacturer: ['manufacturer', 'fabricante', 'marca'],
  serial_number: ['serial_number', 'serial', 'sn', 'numero_serie'],
  rfid: ['rfid', 'tag_rfid', 'etiqueta'],
  quantity: ['quantity', 'quantidade', 'qty', 'qtd'],
  uom: ['uom', 'unidade', 'un', 'unit'],
  project_id: ['project_id', 'id_projeto', 'projeto_id'],
  project_name: ['project_name', 'nome_projeto', 'projeto'],
  client_cnpj: ['client_cnpj', 'cnpj_cliente', 'cnpj'],
  ownership: ['ownership', 'propriedade', 'dono'],
  sap_depot_code: ['sap_depot_code', 'cod_deposito', 'deposito_sap'],
  sap_depot_name: ['sap_depot_name', 'nome_deposito', 'deposito'],
  site: ['site', 'local', 'localidade'],
  location_type: ['location_type', 'tipo_local', 'tipo_deposito'],
  physical_address: ['physical_address', 'endereco', 'address'],
  technician_id: ['technician_id', 'id_tecnico', 'tecnico_id'],
  technician_name: ['technician_name', 'nome_tecnico', 'tecnico'],
  technician_city: ['technician_city', 'cidade_tecnico', 'cidade'],
  technician_state: ['technician_state', 'estado_tecnico', 'uf'],
  status: ['status', 'situacao', 'estado'],
  nf_number: ['nf_number', 'numero_nf', 'nf'],
  nf_date: ['nf_date', 'data_nf', 'data_nota'],
  sap_document: ['sap_document', 'documento_sap', 'doc_sap'],
  sap_posting_date: ['sap_posting_date', 'data_lancamento', 'data_posting'],
  tiflux_ticket_id: ['tiflux_ticket_id', 'chamado_tiflux', 'tiflux'],
  last_inventory_count_date: ['last_inventory_count_date', 'data_ultimo_inventario'],
  notes: ['notes', 'observacoes', 'obs', 'notas'],
};

export const SAP_COLUMN_LABELS: Record<string, string> = {
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
// Hook
// =============================================================================

export function useSAPImport(): UseSAPImportReturn {
  const queryClient = useQueryClient();

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Preview state
  const [preview, setPreview] = useState<SAPImportPreview | null>(null);
  const [pnOverrides, setPnOverrides] = useState<Record<number, string>>({});

  // Result state
  const [result, setResult] = useState<SAPImportResult | null>(null);

  // Upload and preview
  const uploadAndPreview = useCallback(async (
    file: File,
    projectId?: string,
    locationId?: string
  ): Promise<SAPImportPreview> => {
    setIsProcessing(true);
    setProgress(0);
    setError(null);
    setResult(null);
    setPnOverrides({});

    try {
      // Validate file type
      const validExtensions = ['.csv', '.xlsx'];
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      if (!validExtensions.includes(ext)) {
        throw new Error('Formato invalido. Use CSV ou XLSX.');
      }

      setProgress(20);

      // Convert file to base64
      const fileContent = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(',')[1];
          resolve(base64);
        };
        reader.onerror = () => reject(new Error('Erro ao ler arquivo'));
        reader.readAsDataURL(file);
      });

      setProgress(40);

      // Call preview endpoint
      const previewResult = await previewSAPImport({
        file_content: fileContent,
        filename: file.name,
        project_id: projectId,
        destination_location_id: locationId,
        full_asset_creation: true,
      });

      setProgress(100);

      const previewData = previewResult.data as SAPImportPreview;
      setPreview(previewData);

      return previewData;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao processar arquivo';
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // Execute import mutation
  const executeImportMutation = useMutation({
    mutationFn: async () => {
      if (!preview) throw new Error('Nenhum preview disponivel');

      const importResult = await executeSAPImport({
        import_id: preview.import_id,
        pn_overrides: pnOverrides,
        full_asset_creation: true,
      });

      return importResult.data as SAPImportResult;
    },
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      setPnOverrides({});
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
    },
  });

  // Execute import wrapper
  const executeImport = useCallback(async (): Promise<SAPImportResult> => {
    setIsProcessing(true);
    setProgress(0);
    setError(null);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + 10, 90));
      }, 500);

      const result = await executeImportMutation.mutateAsync();

      clearInterval(progressInterval);
      setProgress(100);

      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro na importacao';
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, [executeImportMutation]);

  // Set PN override for a row
  const setPNOverride = useCallback((rowNumber: number, pnId: string) => {
    setPnOverrides(prev => ({
      ...prev,
      [rowNumber]: pnId,
    }));
  }, []);

  // Clear preview
  const clearPreview = useCallback(() => {
    setPreview(null);
    setPnOverrides({});
    setError(null);
    setProgress(0);
    setResult(null);
  }, []);

  // Compute matched/unmatched rows
  const matchedRows = preview?.sample_data.filter(row => row.is_matched) || [];
  const unmatchedRows = preview?.sample_data.filter(row => !row.is_matched) || [];

  return {
    isProcessing,
    progress,
    error,
    preview,
    columnMappings: preview?.column_mappings || [],
    matchedRows,
    unmatchedRows,
    pnOverrides,
    setPNOverride,
    uploadAndPreview,
    executeImport,
    clearPreview,
    result,
  };
}
