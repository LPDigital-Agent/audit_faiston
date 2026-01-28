'use client';

// =============================================================================
// Nova Campanha Page - SGA Inventory Module
// =============================================================================
// Create new inventory counting campaign.
// =============================================================================

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  GlassCard,
  GlassCardHeader,
  GlassCardTitle,
  GlassCardContent,
} from '@/components/shared/glass-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  ClipboardCheck,
  ArrowLeft,
  MapPin,
  Package,
  CheckCircle2,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { useInventoryCount, useAssetManagement } from '@/hooks/ativos';

// =============================================================================
// Page Component
// =============================================================================

export default function NovaCampanhaPage() {
  const router = useRouter();
  const { startNewCampaign } = useInventoryCount();
  const { locations, partNumbers } = useAssetManagement();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [selectedPartNumbers, setSelectedPartNumbers] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Toggle location selection
  const toggleLocation = (locationId: string) => {
    setSelectedLocations(prev =>
      prev.includes(locationId)
        ? prev.filter(id => id !== locationId)
        : [...prev, locationId]
    );
  };

  // Toggle part number selection
  const togglePartNumber = (pnId: string) => {
    setSelectedPartNumbers(prev =>
      prev.includes(pnId)
        ? prev.filter(id => id !== pnId)
        : [...prev, pnId]
    );
  };

  // Select all locations
  const selectAllLocations = () => {
    setSelectedLocations(locations.filter(l => l.is_active && l.type === 'WAREHOUSE').map(l => l.id));
  };

  // Handle submit
  const handleSubmit = async () => {
    if (!name || selectedLocations.length === 0) {
      setError('Preencha todos os campos obrigatórios');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await startNewCampaign({
        name,
        description,
        location_ids: selectedLocations,
        part_numbers: selectedPartNumbers.length > 0 ? selectedPartNumbers : undefined,
      });

      router.push('/ferramentas/ativos/estoque/inventario');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao criar campanha');
    } finally {
      setIsSubmitting(false);
    }
  };

  const warehouseLocations = locations.filter(l => l.is_active && l.type === 'WAREHOUSE');
  const activePartNumbers = partNumbers.filter(p => p.is_active);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/ferramentas/ativos/estoque/inventario">
                <ArrowLeft className="w-4 h-4 mr-1" />
                Inventário
              </Link>
            </Button>
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            Nova Campanha de Inventário
          </h1>
          <p className="text-sm text-text-muted mt-1">
            Configure os parâmetros da contagem
          </p>
        </div>
      </div>

      {/* Form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Basic Info */}
        <div className="lg:col-span-2 space-y-6">
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <ClipboardCheck className="w-4 h-4 text-blue-light" />
                <GlassCardTitle>Informações da Campanha</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Nome da Campanha *
                  </label>
                  <Input
                    placeholder="Ex: Inventário Mensal Janeiro/2026"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="bg-white/5 border-border"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-text-primary mb-2 block">
                    Descrição
                  </label>
                  <textarea
                    className="w-full px-3 py-2 bg-white/5 border border-border rounded-md text-sm text-text-primary min-h-[100px] resize-none"
                    placeholder="Descrição opcional..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />
                </div>

              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Locations */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-green-400" />
                  <GlassCardTitle>Locais a Inventariar *</GlassCardTitle>
                </div>
                <Button variant="ghost" size="sm" onClick={selectAllLocations}>
                  Selecionar Todos
                </Button>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {warehouseLocations.map((location) => (
                  <div
                    key={location.id}
                    onClick={() => toggleLocation(location.id)}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedLocations.includes(location.id)
                        ? 'bg-green-500/20 border-green-500/50'
                        : 'bg-white/5 border-border hover:border-blue-mid/50'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded border flex items-center justify-center ${
                        selectedLocations.includes(location.id)
                          ? 'bg-green-500 border-green-500'
                          : 'border-text-muted'
                      }`}>
                        {selectedLocations.includes(location.id) && (
                          <CheckCircle2 className="w-3 h-3 text-white" />
                        )}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {location.code}
                        </p>
                        <p className="text-xs text-text-muted">{location.name}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {selectedLocations.length > 0 && (
                <p className="text-sm text-text-muted mt-4">
                  {selectedLocations.length} local(is) selecionado(s)
                </p>
              )}
            </GlassCardContent>
          </GlassCard>
        </div>

        {/* Right Column - Summary & Submit */}
        <div className="space-y-6">
          {/* Part Number Filter (Optional) */}
          <GlassCard>
            <GlassCardHeader>
              <div className="flex items-center gap-2">
                <Package className="w-4 h-4 text-blue-light" />
                <GlassCardTitle>Filtrar por PN</GlassCardTitle>
              </div>
            </GlassCardHeader>

            <GlassCardContent>
              <p className="text-xs text-text-muted mb-3">
                Opcional: selecione PNs específicos ou deixe vazio para contar todos.
              </p>
              <div className="max-h-[200px] overflow-y-auto space-y-1">
                {activePartNumbers.slice(0, 10).map((pn) => (
                  <div
                    key={pn.id}
                    onClick={() => togglePartNumber(pn.part_number)}
                    className={`p-2 rounded cursor-pointer text-sm ${
                      selectedPartNumbers.includes(pn.part_number)
                        ? 'bg-blue-mid/20 text-blue-light'
                        : 'hover:bg-white/5 text-text-muted'
                    }`}
                  >
                    {pn.part_number}
                  </div>
                ))}
              </div>
              {selectedPartNumbers.length > 0 && (
                <Badge variant="outline" className="mt-2">
                  {selectedPartNumbers.length} PN(s) selecionado(s)
                </Badge>
              )}
            </GlassCardContent>
          </GlassCard>

          {/* Summary */}
          <GlassCard>
            <GlassCardHeader>
              <GlassCardTitle>Resumo</GlassCardTitle>
            </GlassCardHeader>

            <GlassCardContent>
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Nome:</span>
                  <span className="text-text-primary">{name || '-'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Locais:</span>
                  <span className="text-text-primary">{selectedLocations.length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-text-muted">Filtros PN:</span>
                  <span className="text-text-primary">
                    {selectedPartNumbers.length > 0 ? selectedPartNumbers.length : 'Todos'}
                  </span>
                </div>
              </div>
            </GlassCardContent>
          </GlassCard>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/20 border border-red-500/30 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-red-400" />
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <Button
            className="w-full"
            disabled={!name || selectedLocations.length === 0 || isSubmitting}
            onClick={handleSubmit}
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Criando...
              </>
            ) : (
              <>
                <ClipboardCheck className="w-4 h-4 mr-2" />
                Criar Campanha
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
