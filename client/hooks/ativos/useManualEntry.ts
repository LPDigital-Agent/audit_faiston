// =============================================================================
// useManualEntry Hook - SGA Inventory Module
// =============================================================================
// Manual material entry without source file.
// Handles direct entry with multiple items, serial numbers, and values.
// =============================================================================

'use client';

import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createManualEntry } from '@/services/sgaAgentcore';

// =============================================================================
// Types
// =============================================================================

export interface ManualEntryItem {
  id: string;
  part_number_id: string;
  part_number_code: string;
  quantity: number;
  serial_numbers: string;
  unit_value: number;
  notes: string;
}

export interface ManualEntryRequest {
  items: ManualEntryItem[];
  project_id?: string;
  destination_location_id: string;
  document_reference?: string;
  notes?: string;
}

export interface ManualEntryResult {
  success: boolean;
  entry_id: string;
  movements_created: number;
  assets_created: number;
  total_quantity: number;
  errors: string[];
  warnings: string[];
}

export interface UseManualEntryReturn {
  // Processing state
  isProcessing: boolean;
  error: string | null;

  // Items state
  items: ManualEntryItem[];
  addItem: () => void;
  removeItem: (id: string) => void;
  updateItem: (id: string, field: keyof ManualEntryItem, value: string | number) => void;
  clearItems: () => void;

  // Actions
  submitEntry: (params: Omit<ManualEntryRequest, 'items'>) => Promise<ManualEntryResult>;

  // Result
  result: ManualEntryResult | null;
  clearResult: () => void;

  // Computed
  totalItems: number;
  totalQuantity: number;
  isValid: boolean;
}

// =============================================================================
// Hook
// =============================================================================

export function useManualEntry(): UseManualEntryReturn {
  const queryClient = useQueryClient();

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Items state
  const [items, setItems] = useState<ManualEntryItem[]>([
    createEmptyItem(),
  ]);

  // Result state
  const [result, setResult] = useState<ManualEntryResult | null>(null);

  // Create empty item helper
  function createEmptyItem(): ManualEntryItem {
    return {
      id: crypto.randomUUID(),
      part_number_id: '',
      part_number_code: '',
      quantity: 1,
      serial_numbers: '',
      unit_value: 0,
      notes: '',
    };
  }

  // Add new item
  const addItem = useCallback(() => {
    setItems(prev => [...prev, createEmptyItem()]);
  }, []);

  // Remove item
  const removeItem = useCallback((id: string) => {
    setItems(prev => {
      // Keep at least one item
      if (prev.length <= 1) return prev;
      return prev.filter(item => item.id !== id);
    });
  }, []);

  // Update item
  const updateItem = useCallback((
    id: string,
    field: keyof ManualEntryItem,
    value: string | number
  ) => {
    setItems(prev =>
      prev.map(item => {
        if (item.id !== id) return item;
        return { ...item, [field]: value };
      })
    );
  }, []);

  // Clear all items (reset to single empty item)
  const clearItems = useCallback(() => {
    setItems([createEmptyItem()]);
    setError(null);
  }, []);

  // Submit entry mutation
  const submitEntryMutation = useMutation({
    mutationFn: async (params: ManualEntryRequest) => {
      // Filter valid items
      const validItems = params.items.filter(
        item => item.part_number_id && item.quantity > 0
      );

      if (validItems.length === 0) {
        throw new Error('Adicione pelo menos um item valido');
      }

      // Transform items for API
      const apiItems = validItems.map(item => ({
        part_number_id: item.part_number_id,
        quantity: item.quantity,
        serial_numbers: item.serial_numbers
          ? item.serial_numbers.split(',').map(s => s.trim()).filter(Boolean)
          : undefined,
        unit_value: item.unit_value > 0 ? item.unit_value : undefined,
        notes: item.notes || undefined,
      }));

      const response = await createManualEntry({
        items: apiItems,
        project_id: params.project_id,
        destination_location_id: params.destination_location_id,
        document_reference: params.document_reference,
        notes: params.notes,
      });

      return response.data as ManualEntryResult;
    },
    onSuccess: (data) => {
      setResult(data);
      setItems([createEmptyItem()]);
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['sga-assets'] });
      queryClient.invalidateQueries({ queryKey: ['sga-balance'] });
      queryClient.invalidateQueries({ queryKey: ['sga-movements'] });
    },
  });

  // Submit entry wrapper
  const submitEntry = useCallback(async (
    params: Omit<ManualEntryRequest, 'items'>
  ): Promise<ManualEntryResult> => {
    setIsProcessing(true);
    setError(null);

    try {
      const result = await submitEntryMutation.mutateAsync({
        ...params,
        items,
      });
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erro ao registrar entrada';
      setError(message);
      throw err;
    } finally {
      setIsProcessing(false);
    }
  }, [submitEntryMutation, items]);

  // Clear result
  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  // Computed values
  const validItems = items.filter(item => item.part_number_id && item.quantity > 0);
  const totalItems = validItems.length;
  const totalQuantity = items.reduce((sum, item) => sum + (item.quantity || 0), 0);
  const isValid = totalItems > 0;

  return {
    isProcessing,
    error,
    items,
    addItem,
    removeItem,
    updateItem,
    clearItems,
    submitEntry,
    result,
    clearResult,
    totalItems,
    totalQuantity,
    isValid,
  };
}
