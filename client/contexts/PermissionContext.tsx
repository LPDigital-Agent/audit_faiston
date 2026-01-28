'use client';

/**
 * @file PermissionContext.tsx
 * @description React Context for managing user permissions in Faiston NEXO
 *
 * This context provides:
 * - Centralized permission state management
 * - Permission checking methods
 * - Module access validation
 * - Route protection utilities
 *
 * Use the usePermissions() hook to access the context.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import { useAuth } from './AuthContext';
import {
  fetchPermissions,
  validatePermissionsHash,
  getRoutePermission,
  type PermissionResponse,
} from '@/services/permissionService';

// =============================================================================
// Types
// =============================================================================

/** Permission state */
interface PermissionState {
  /** User's profile ID */
  profileId: string | null;

  /** User's profile display name */
  profileName: string | null;

  /** Base profile (ADMIN, LOGISTICA, TECNICO, FINANCEIRO) */
  baseProfile: string | null;

  /** Set of permission codes the user has */
  permissions: Set<string>;

  /** Profile version for cache invalidation */
  version: number;

  /** Permissions hash for integrity validation */
  hash: string;

  /** Whether permissions are loaded */
  isLoaded: boolean;

  /** Whether permissions are loading */
  isLoading: boolean;

  /** Error message if loading failed */
  error: string | null;
}

/** Permission context with methods */
interface PermissionContextType extends PermissionState {
  /** Check if user has a specific permission */
  hasPermission: (code: string) => boolean;

  /** Check if user has any of the specified permissions */
  hasAnyPermission: (codes: string[]) => boolean;

  /** Check if user has all specified permissions */
  hasAllPermissions: (codes: string[]) => boolean;

  /** Check if user can access a module */
  canAccessModule: (module: string) => boolean;

  /** Check if user can access a route */
  canAccessRoute: (route: string) => boolean;

  /** Reload permissions from backend */
  reloadPermissions: () => Promise<void>;

  /** Check if user is admin */
  isAdmin: boolean;
}

// =============================================================================
// Initial State
// =============================================================================

const initialState: PermissionState = {
  profileId: null,
  profileName: null,
  baseProfile: null,
  permissions: new Set(),
  version: 0,
  hash: '',
  isLoaded: false,
  isLoading: false,
  error: null,
};

// =============================================================================
// Context
// =============================================================================

const PermissionContext = createContext<PermissionContextType | undefined>(undefined);

// =============================================================================
// Module Access Configuration
// =============================================================================

/** Module codes that each base profile can access */
const MODULE_ACCESS: Record<string, string[]> = {
  admin: ['*'], // Admin can access everything
  logistica: ['AUTH', 'INTRA', 'NEXO', 'EST', 'MOV', 'EXP', 'REV', 'INV', 'CAD', 'TRANSP', 'DISP', 'ACAD'],
  tecnico: ['AUTH', 'INTRA', 'NEXO', 'EST', 'MOV', 'INV', 'DISP', 'ACAD'],
  financeiro: ['AUTH', 'INTRA', 'NEXO', 'EST', 'FISC', 'ACAD'],
};

// =============================================================================
// Provider
// =============================================================================

interface PermissionProviderProps {
  children: ReactNode;
}

/**
 * Permission Provider component.
 *
 * Wraps the application to provide permission context.
 * Should be placed inside AuthProvider.
 *
 * @example
 * ```tsx
 * // app/layout.tsx
 * export default function RootLayout({ children }) {
 *   return (
 *     <AuthProvider>
 *       <PermissionProvider>
 *         {children}
 *       </PermissionProvider>
 *     </AuthProvider>
 *   );
 * }
 * ```
 */
export const PermissionProvider: React.FC<PermissionProviderProps> = ({ children }) => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [state, setState] = useState<PermissionState>(initialState);

  // ===========================================================================
  // Load Permissions
  // ===========================================================================

  const loadPermissions = useCallback(async () => {
    if (!isAuthenticated) {
      setState(initialState);
      return;
    }

    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const response: PermissionResponse = await fetchPermissions();

      // Validate hash integrity
      const isValid = await validatePermissionsHash(response.permissions, response.hash);
      if (!isValid) {
        console.warn('Permission hash validation failed');
      }

      setState({
        profileId: response.profileId,
        profileName: response.profileName,
        baseProfile: response.baseProfile,
        permissions: new Set(response.permissions),
        version: response.version,
        hash: response.hash,
        isLoaded: true,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      console.error('[Permissions] Error loading permissions:', error);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        isLoaded: true,
        error: error instanceof Error ? error.message : 'Failed to load permissions',
      }));
    }
  }, [isAuthenticated]);

  // Load permissions when authenticated
  useEffect(() => {
    if (!authLoading && isAuthenticated && !state.isLoaded && !state.isLoading) {
      loadPermissions();
    } else if (!authLoading && !isAuthenticated && state.isLoaded) {
      // Clear permissions when logged out
      setState(initialState);
    }
  }, [authLoading, isAuthenticated, state.isLoaded, state.isLoading, loadPermissions]);

  // ===========================================================================
  // Permission Methods
  // ===========================================================================

  /**
   * Check if user has a specific permission.
   */
  const hasPermission = useCallback(
    (code: string): boolean => {
      // Admin has all permissions
      if (state.baseProfile === 'admin' || state.permissions.has('*')) {
        return true;
      }

      return state.permissions.has(code);
    },
    [state.baseProfile, state.permissions]
  );

  /**
   * Check if user has any of the specified permissions.
   */
  const hasAnyPermission = useCallback(
    (codes: string[]): boolean => {
      if (state.baseProfile === 'admin' || state.permissions.has('*')) {
        return true;
      }

      return codes.some((code) => state.permissions.has(code));
    },
    [state.baseProfile, state.permissions]
  );

  /**
   * Check if user has all specified permissions.
   */
  const hasAllPermissions = useCallback(
    (codes: string[]): boolean => {
      if (state.baseProfile === 'admin' || state.permissions.has('*')) {
        return true;
      }

      return codes.every((code) => state.permissions.has(code));
    },
    [state.baseProfile, state.permissions]
  );

  /**
   * Check if user can access a module.
   */
  const canAccessModule = useCallback(
    (module: string): boolean => {
      if (!state.baseProfile) {
        return false;
      }

      const allowedModules = MODULE_ACCESS[state.baseProfile] || [];

      // Admin or wildcard
      if (allowedModules.includes('*')) {
        return true;
      }

      return allowedModules.includes(module);
    },
    [state.baseProfile]
  );

  /**
   * Check if user can access a route.
   */
  const canAccessRoute = useCallback(
    (route: string): boolean => {
      // Admin can access everything
      if (state.baseProfile === 'admin') {
        return true;
      }

      const requiredPermission = getRoutePermission(route);

      // No permission required for this route
      if (!requiredPermission) {
        return true;
      }

      return hasPermission(requiredPermission);
    },
    [state.baseProfile, hasPermission]
  );

  /**
   * Reload permissions from backend.
   */
  const reloadPermissions = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoaded: false }));
    await loadPermissions();
  }, [loadPermissions]);

  /**
   * Check if user is admin.
   */
  const isAdmin = useMemo(() => state.baseProfile === 'admin', [state.baseProfile]);

  // ===========================================================================
  // Context Value
  // ===========================================================================

  const value: PermissionContextType = useMemo(
    () => ({
      ...state,
      hasPermission,
      hasAnyPermission,
      hasAllPermissions,
      canAccessModule,
      canAccessRoute,
      reloadPermissions,
      isAdmin,
    }),
    [
      state,
      hasPermission,
      hasAnyPermission,
      hasAllPermissions,
      canAccessModule,
      canAccessRoute,
      reloadPermissions,
      isAdmin,
    ]
  );

  return <PermissionContext.Provider value={value}>{children}</PermissionContext.Provider>;
};

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook to access the permission context.
 *
 * @returns Permission context with state and methods
 * @throws Error if used outside PermissionProvider
 *
 * @example
 * ```tsx
 * function EditButton() {
 *   const { hasPermission } = usePermissions();
 *
 *   if (!hasPermission('EST_U01')) {
 *     return null;
 *   }
 *
 *   return <Button>Editar</Button>;
 * }
 * ```
 */
export const usePermissions = (): PermissionContextType => {
  const context = useContext(PermissionContext);

  if (context === undefined) {
    throw new Error('usePermissions deve ser usado dentro de um PermissionProvider');
  }

  return context;
};

export default PermissionContext;
