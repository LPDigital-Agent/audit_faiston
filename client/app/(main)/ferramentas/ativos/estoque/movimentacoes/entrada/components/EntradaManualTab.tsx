'use client';

// =============================================================================
// EntradaManualTab - Manual Entry Tab Component
// =============================================================================
// Handles direct manual entry of materials without any source file.
// Allows adding multiple items in a single entry operation.
// =============================================================================

import { useState, useCallback } from 'react';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  PenLine,
  Plus,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Package,
  MapPin,
  Briefcase,
  Clock,
  Hash,
  FileText,
} from 'lucide-react';
import type { SGAProject, SGALocation, SGAPartNumber } from '@/lib/ativos/types';

// Type aliases for cleaner code
type Project = SGAProject;
type Location = SGALocation;
type PartNumber = SGAPartNumber;

// =============================================================================
// Types
// =============================================================================

interface ManualEntryItem {
  id: string;
  part_number_id: string;
  part_number_code: string;
  quantity: number;
  serial_numbers: string;
  unit_value: number;
  notes: string;
}

interface EntradaManualTabProps {
  // Processing state
  isProcessing: boolean;
  error: string | null;

  // Master data
  projects: Project[];
  locations: Location[];
  partNumbers: PartNumber[];

  // Actions
  onSubmit: (params: {
    items: ManualEntryItem[];
    project_id?: string;
    destination_location_id: string;
    document_reference?: string;
    notes?: string;
  }) => Promise<void>;
  onClear: () => void;
}

// =============================================================================
// Component
// =============================================================================

export function EntradaManualTab({
  isProcessing,
  error,
  projects,
  locations,
  partNumbers,
  onSubmit,
  onClear,
}: EntradaManualTabProps) {
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('');
  const [documentReference, setDocumentReference] = useState('');
  const [generalNotes, setGeneralNotes] = useState('');
  const [items, setItems] = useState<ManualEntryItem[]>([
    {
      id: crypto.randomUUID(),
      part_number_id: '',
      part_number_code: '',
      quantity: 1,
      serial_numbers: '',
      unit_value: 0,
      notes: '',
    },
  ]);

  // Add new item
  const addItem = useCallback(() => {
    setItems((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        part_number_id: '',
        part_number_code: '',
        quantity: 1,
        serial_numbers: '',
        unit_value: 0,
        notes: '',
      },
    ]);
  }, []);

  // Remove item
  const removeItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  // Update item
  const updateItem = useCallback((id: string, field: keyof ManualEntryItem, value: string | number) => {
    setItems((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;

        // If updating part_number_id, also update the code
        if (field === 'part_number_id') {
          const pn = partNumbers.find((p) => p.id === value);
          return {
            ...item,
            part_number_id: value as string,
            part_number_code: pn?.part_number || '',
          };
        }

        return { ...item, [field]: value };
      })
    );
  }, [partNumbers]);

  // Handle submit
  const handleSubmit = async () => {
    if (!selectedLocation || items.length === 0) return;

    // Validate items
    const validItems = items.filter((item) => item.part_number_id && item.quantity > 0);
    if (validItems.length === 0) {
      return;
    }

    try {
      await onSubmit({
        items: validItems,
        project_id: selectedProject || undefined,
        destination_location_id: selectedLocation,
        document_reference: documentReference || undefined,
        notes: generalNotes || undefined,
      });

      // Clear form on success
      setItems([
        {
          id: crypto.randomUUID(),
          part_number_id: '',
          part_number_code: '',
          quantity: 1,
          serial_numbers: '',
          unit_value: 0,
          notes: '',
        },
      ]);
      setSelectedProject('');
      setSelectedLocation('');
      setDocumentReference('');
      setGeneralNotes('');
    } catch {
      // Error handled by hook
    }
  };

  // Calculate totals
  const totalItems = items.filter((item) => item.part_number_id).length;
  const totalQuantity = items.reduce((sum, item) => sum + (item.quantity || 0), 0);

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-purple-500/10 border border-purple-500/20 rounded-lg">
        <PenLine className="w-5 h-5 text-purple-400 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-purple-400">
            Entrada Manual de Materiais
          </p>
          <p className="text-xs text-purple-400/80 mt-1">
            Registre entradas sem arquivo de origem. Ideal para recebimentos avulsos,
            doacoes ou ajustes de estoque.
          </p>
        </div>
      </div>

      {/* Header Section */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-purple-400" />
            <GlassCardTitle>Informacoes da Entrada</GlassCardTitle>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          <div className="space-y-4">
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
                  Local de Destino <span className="text-red-400">*</span>
                </label>
                <select
                  className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                  value={selectedLocation}
                  onChange={(e) => setSelectedLocation(e.target.value)}
                >
                  <option value="">Selecione o local...</option>
                  {locations.filter(l => l.is_active).map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.code} - {location.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  <Hash className="w-4 h-4 inline mr-2" />
                  Referencia/Documento <span className="text-text-muted font-normal">(opcional)</span>
                </label>
                <Input
                  placeholder="Ex: NF 12345, Remessa 001..."
                  value={documentReference}
                  onChange={(e) => setDocumentReference(e.target.value)}
                  className="bg-white/5 border-border"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-text-primary mb-2 block">
                  Observacoes Gerais <span className="text-text-muted font-normal">(opcional)</span>
                </label>
                <Input
                  placeholder="Observacoes da entrada..."
                  value={generalNotes}
                  onChange={(e) => setGeneralNotes(e.target.value)}
                  className="bg-white/5 border-border"
                />
              </div>
            </div>
          </div>
        </GlassCardContent>
      </GlassCard>

      {/* Items Section */}
      <GlassCard>
        <GlassCardHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Package className="w-4 h-4 text-purple-400" />
              <GlassCardTitle>Itens da Entrada</GlassCardTitle>
              <Badge variant="outline">{totalItems} itens</Badge>
            </div>
            <Button size="sm" variant="outline" onClick={addItem}>
              <Plus className="w-4 h-4 mr-1" />
              Adicionar Item
            </Button>
          </div>
        </GlassCardHeader>

        <GlassCardContent>
          <div className="space-y-4">
            {items.map((item, index) => (
              <div
                key={item.id}
                className="p-4 bg-white/5 rounded-lg border border-border/50"
              >
                <div className="flex items-center justify-between mb-4">
                  <span className="text-sm font-medium text-text-muted">
                    Item #{index + 1}
                  </span>
                  {items.length > 1 && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      onClick={() => removeItem(item.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="md:col-span-2">
                    <label className="text-xs text-text-muted mb-1 block">
                      Part Number <span className="text-red-400">*</span>
                    </label>
                    <select
                      className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary"
                      value={item.part_number_id}
                      onChange={(e) => updateItem(item.id, 'part_number_id', e.target.value)}
                    >
                      <option value="">Selecione o PN...</option>
                      {partNumbers.filter(pn => pn.is_active).map((pn) => (
                        <option key={pn.id} value={pn.id}>
                          {pn.part_number} - {pn.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-text-muted mb-1 block">
                      Quantidade <span className="text-red-400">*</span>
                    </label>
                    <Input
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={(e) => updateItem(item.id, 'quantity', parseInt(e.target.value) || 1)}
                      className="bg-white/5 border-border"
                    />
                  </div>

                  <div>
                    <label className="text-xs text-text-muted mb-1 block">
                      Valor Unit. (R$)
                    </label>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={item.unit_value}
                      onChange={(e) => updateItem(item.id, 'unit_value', parseFloat(e.target.value) || 0)}
                      className="bg-white/5 border-border"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">
                      Numeros de Serie (separados por virgula)
                    </label>
                    <Input
                      placeholder="SN001, SN002, SN003..."
                      value={item.serial_numbers}
                      onChange={(e) => updateItem(item.id, 'serial_numbers', e.target.value)}
                      className="bg-white/5 border-border"
                    />
                  </div>

                  <div>
                    <label className="text-xs text-text-muted mb-1 block">
                      Observacoes do Item
                    </label>
                    <Input
                      placeholder="Notas sobre este item..."
                      value={item.notes}
                      onChange={(e) => updateItem(item.id, 'notes', e.target.value)}
                      className="bg-white/5 border-border"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCardContent>
      </GlassCard>

      {/* Summary */}
      <div className="flex items-center justify-between p-4 bg-white/5 rounded-lg border border-border">
        <div className="flex items-center gap-6">
          <div>
            <p className="text-xs text-text-muted">Total de Itens</p>
            <p className="text-lg font-semibold text-text-primary">{totalItems}</p>
          </div>
          <div>
            <p className="text-xs text-text-muted">Quantidade Total</p>
            <p className="text-lg font-semibold text-text-primary">{totalQuantity}</p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-red-400" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={onClear} className="flex-1">
          Limpar
        </Button>
        <Button
          onClick={handleSubmit}
          className="flex-1 bg-gradient-to-r from-purple-600 to-purple-500"
          disabled={!selectedLocation || totalItems === 0 || isProcessing}
        >
          {isProcessing ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Registrando...
            </>
          ) : (
            <>
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Registrar Entrada ({totalItems} itens)
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
