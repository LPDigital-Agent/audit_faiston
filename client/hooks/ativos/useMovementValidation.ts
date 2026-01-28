// =============================================================================
// useMovementValidation Hook - SGA Inventory Module
// =============================================================================
// Pre-validation of movement operations before execution.
// Checks compliance rules, restrictions, and approval requirements.
// =============================================================================


import { useState, useCallback } from 'react';
import { useInventoryOperations } from '@/contexts/ativos';
import type { SGAMovementType, ComplianceValidation } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface ValidationParams {
  operationType: SGAMovementType;
  partNumber: string;
  quantity: number;
  sourceLocationId?: string;
  destinationLocationId?: string;
  projectId?: string;
}

interface UseMovementValidationReturn {
  // Validation state
  validation: ComplianceValidation | null;
  isValidating: boolean;
  validationError: string | null;

  // Derived state
  isValid: boolean;
  requiresApproval: boolean;
  approvalRole: string | null;
  violations: string[];
  warnings: string[];

  // Actions
  validate: (params: ValidationParams) => Promise<ComplianceValidation>;
  clearValidation: () => void;
}

// =============================================================================
// Hook
// =============================================================================

export function useMovementValidation(): UseMovementValidationReturn {
  const { validateMovement, operationError, resetOperation } = useInventoryOperations();

  const [isValidating, setIsValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ComplianceValidation | null>(null);

  // Validate movement
  const validate = useCallback(async (params: ValidationParams): Promise<ComplianceValidation> => {
    setIsValidating(true);
    setValidationError(null);

    try {
      const result = await validateMovement(
        params.operationType,
        params.partNumber,
        params.quantity,
        params.sourceLocationId,
        params.destinationLocationId,
        params.projectId
      );

      setValidation(result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Erro na validacao';
      setValidationError(message);
      throw error;
    } finally {
      setIsValidating(false);
    }
  }, [validateMovement]);

  // Clear validation state
  const clearValidation = useCallback(() => {
    setValidation(null);
    setValidationError(null);
    resetOperation();
  }, [resetOperation]);

  // Derived state
  const isValid = validation?.is_valid ?? false;
  const requiresApproval = validation?.requires_approval ?? false;
  const approvalRole = validation?.approval_role ?? null;
  const violations = validation?.violations.map(v => v.description) ?? [];
  const warnings = validation?.warnings ?? [];

  return {
    validation,
    isValidating,
    validationError: validationError || operationError,
    isValid,
    requiresApproval,
    approvalRole,
    violations,
    warnings,
    validate,
    clearValidation,
  };
}

// Re-export types
export type { SGAMovementType, ComplianceValidation };
