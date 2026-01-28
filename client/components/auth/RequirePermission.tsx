'use client';

/**
 * @file RequirePermission.tsx
 * @description Components for permission-based rendering and route protection
 *
 * Provides:
 * - RequirePermission: Conditionally render content based on permissions
 * - RequireAnyPermission: Require at least one permission
 * - RequireAllPermissions: Require all permissions
 * - RequireModuleAccess: Require module access
 * - ProtectedByPermission: Route-level protection with redirect
 */

import { type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { usePermissions } from '@/contexts/PermissionContext';
import { Loader2, Lock } from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface RequirePermissionProps {
  /** Permission code required */
  code: string;

  /** Content to render if permission granted */
  children: ReactNode;

  /** Content to render if permission denied (default: null) */
  fallback?: ReactNode;

  /** Whether to show loading state while permissions load */
  showLoading?: boolean;
}

interface RequireAnyPermissionProps {
  /** Permission codes (at least one required) */
  codes: string[];

  /** Content to render if any permission granted */
  children: ReactNode;

  /** Content to render if all permissions denied */
  fallback?: ReactNode;

  /** Whether to show loading state while permissions load */
  showLoading?: boolean;
}

interface RequireAllPermissionsProps {
  /** Permission codes (all required) */
  codes: string[];

  /** Content to render if all permissions granted */
  children: ReactNode;

  /** Content to render if any permission denied */
  fallback?: ReactNode;

  /** Whether to show loading state while permissions load */
  showLoading?: boolean;
}

interface RequireModuleAccessProps {
  /** Module code */
  module: string;

  /** Content to render if module access granted */
  children: ReactNode;

  /** Content to render if access denied */
  fallback?: ReactNode;

  /** Whether to show loading state while permissions load */
  showLoading?: boolean;
}

interface ProtectedByPermissionProps {
  /** Permission code required */
  code: string;

  /** Content to render if permission granted */
  children: ReactNode;

  /** Redirect route if permission denied (default: /unauthorized) */
  redirectTo?: string;

  /** Custom loading component */
  loadingComponent?: ReactNode;

  /** Custom unauthorized component (shown briefly before redirect) */
  unauthorizedComponent?: ReactNode;
}

// =============================================================================
// Loading Component
// =============================================================================

function DefaultLoadingSpinner() {
  return (
    <div className="flex items-center justify-center p-4">
      <Loader2 className="w-4 h-4 animate-spin text-text-secondary" />
    </div>
  );
}

// =============================================================================
// Unauthorized Component
// =============================================================================

function DefaultUnauthorized() {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <Lock className="w-12 h-12 text-text-secondary mb-4" />
      <h2 className="text-lg font-semibold text-text-primary mb-2">Acesso Restrito</h2>
      <p className="text-sm text-text-secondary">Você não tem permissão para acessar este conteúdo.</p>
    </div>
  );
}

// =============================================================================
// RequirePermission Component
// =============================================================================

/**
 * Conditionally render content based on a single permission.
 *
 * @example
 * ```tsx
 * <RequirePermission code="EST_C01">
 *   <Button onClick={createAsset}>Criar Ativo</Button>
 * </RequirePermission>
 * ```
 */
export function RequirePermission({
  code,
  children,
  fallback = null,
  showLoading = false,
}: RequirePermissionProps) {
  const { hasPermission, isLoading, isLoaded } = usePermissions();

  if (isLoading || !isLoaded) {
    return showLoading ? <DefaultLoadingSpinner /> : null;
  }

  if (!hasPermission(code)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

// =============================================================================
// RequireAnyPermission Component
// =============================================================================

/**
 * Conditionally render content if user has at least one of the permissions.
 *
 * @example
 * ```tsx
 * <RequireAnyPermission codes={['EST_R01', 'EST_R02', 'EST_R03']}>
 *   <InventoryDashboard />
 * </RequireAnyPermission>
 * ```
 */
export function RequireAnyPermission({
  codes,
  children,
  fallback = null,
  showLoading = false,
}: RequireAnyPermissionProps) {
  const { hasAnyPermission, isLoading, isLoaded } = usePermissions();

  if (isLoading || !isLoaded) {
    return showLoading ? <DefaultLoadingSpinner /> : null;
  }

  if (!hasAnyPermission(codes)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

// =============================================================================
// RequireAllPermissions Component
// =============================================================================

/**
 * Conditionally render content if user has all specified permissions.
 *
 * @example
 * ```tsx
 * <RequireAllPermissions codes={['EST_C01', 'EST_U01', 'EST_D01']}>
 *   <BulkOperationsPanel />
 * </RequireAllPermissions>
 * ```
 */
export function RequireAllPermissions({
  codes,
  children,
  fallback = null,
  showLoading = false,
}: RequireAllPermissionsProps) {
  const { hasAllPermissions, isLoading, isLoaded } = usePermissions();

  if (isLoading || !isLoaded) {
    return showLoading ? <DefaultLoadingSpinner /> : null;
  }

  if (!hasAllPermissions(codes)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

// =============================================================================
// RequireModuleAccess Component
// =============================================================================

/**
 * Conditionally render content based on module access.
 *
 * This is a fast-path check based on the user's base profile,
 * without checking specific permissions.
 *
 * @example
 * ```tsx
 * <RequireModuleAccess module="EST">
 *   <InventoryModule />
 * </RequireModuleAccess>
 * ```
 */
export function RequireModuleAccess({
  module,
  children,
  fallback = null,
  showLoading = false,
}: RequireModuleAccessProps) {
  const { canAccessModule, isLoading, isLoaded } = usePermissions();

  if (isLoading || !isLoaded) {
    return showLoading ? <DefaultLoadingSpinner /> : null;
  }

  if (!canAccessModule(module)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

// =============================================================================
// ProtectedByPermission Component
// =============================================================================

/**
 * Route-level protection with redirect if permission denied.
 *
 * Similar to ProtectedRoute but checks specific permissions instead
 * of just authentication.
 *
 * @example
 * ```tsx
 * export default function AdminPage() {
 *   return (
 *     <ProtectedByPermission code="ADMIN_R01" redirectTo="/dashboard">
 *       <AdminPanel />
 *     </ProtectedByPermission>
 *   );
 * }
 * ```
 */
export function ProtectedByPermission({
  code,
  children,
  redirectTo = '/unauthorized',
  loadingComponent,
  unauthorizedComponent,
}: ProtectedByPermissionProps) {
  const router = useRouter();
  const { hasPermission, isLoading, isLoaded } = usePermissions();

  // Loading state
  if (isLoading || !isLoaded) {
    return loadingComponent || <DefaultLoadingSpinner />;
  }

  // Permission denied - redirect
  if (!hasPermission(code)) {
    // Show unauthorized briefly before redirect
    if (typeof window !== 'undefined') {
      // Use setTimeout to allow the component to render before redirecting
      setTimeout(() => {
        router.push(redirectTo);
      }, 100);
    }
    return unauthorizedComponent || <DefaultUnauthorized />;
  }

  // Permission granted
  return <>{children}</>;
}

// =============================================================================
// Utility Hook for Route Protection
// =============================================================================

/**
 * Hook to check if user can access the current route.
 *
 * @param route - Route path to check
 * @returns Object with canAccess boolean and isLoading state
 *
 * @example
 * ```tsx
 * function MyPage() {
 *   const { canAccess, isLoading } = useRoutePermission('/admin/usuarios');
 *
 *   if (isLoading) return <Loading />;
 *   if (!canAccess) return <Redirect to="/unauthorized" />;
 *
 *   return <PageContent />;
 * }
 * ```
 */
export function useRoutePermission(route: string) {
  const { canAccessRoute, isLoading, isLoaded } = usePermissions();

  return {
    canAccess: canAccessRoute(route),
    isLoading: isLoading || !isLoaded,
  };
}

// =============================================================================
// Exports
// =============================================================================

export default RequirePermission;
