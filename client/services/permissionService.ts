/**
 * @file permissionService.ts
 * @description Service for fetching and managing user permissions
 *
 * This service handles:
 * - Fetching permissions from the backend
 * - Caching permissions in memory
 * - Hash validation for integrity
 * - Permission checks
 */

import { getIdToken } from './authService';

// =============================================================================
// Types
// =============================================================================

/** Permission response from backend */
export interface PermissionResponse {
  profileId: string | null;
  profileName: string | null;
  baseProfile: string | null;
  permissions: string[];
  version: number;
  hash: string;
}

/** Module with access information */
export interface ModuleAccess {
  code: string;
  name: string;
  fullName?: string;
  icon?: string;
  order: number;
  hasAccess: boolean;
}

/** Functionality with permission status */
export interface FunctionalityAccess {
  code: string;
  name: string;
  module: string;
  submodule?: string;
  operation: string;
  route?: string;
  hasPermission: boolean;
}

// =============================================================================
// Configuration
// =============================================================================

// Base URL for permissions API
const PERMISSIONS_API_URL = process.env.NEXT_PUBLIC_AGENTCORE_URL || '';

// =============================================================================
// Permission Service
// =============================================================================

/**
 * Fetch user permissions from the backend.
 *
 * This function is called once after login to get the full
 * list of permissions for the authenticated user.
 *
 * @returns Permission response with profile and permissions
 * @throws Error if fetch fails or user is not authenticated
 */
export async function fetchPermissions(): Promise<PermissionResponse> {
  const idToken = await getIdToken();

  if (!idToken) {
    throw new Error('Usuário não autenticado');
  }

  // For now, we'll decode the token to get basic permission info
  // In a full implementation, this would call the backend API
  try {
    const claims = decodeJwt(idToken);

    // Extract profile info from custom claims
    const profileIdClaim = claims['custom:profile_id'];
    const profileId =
      (typeof profileIdClaim === 'string' ? profileIdClaim : null) ||
      getProfileFromGroups(claims);
    const profileVersionClaim = claims['custom:profile_version'];
    const profileVersion = parseInt(
      typeof profileVersionClaim === 'string' ? profileVersionClaim : '1',
      10
    );
    const permissionsHashClaim = claims['custom:permissions_hash'];
    const permissionsHash =
      typeof permissionsHashClaim === 'string' ? permissionsHashClaim : '';

    // If we have a backend endpoint, call it
    if (PERMISSIONS_API_URL) {
      const response = await fetch(`${PERMISSIONS_API_URL}/auth/permissions`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${idToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch permissions: ${response.status}`);
      }

      const data: PermissionResponse = await response.json();

      // Validate hash if provided in token
      if (permissionsHash && data.hash !== permissionsHash) {
        console.warn('Permission hash mismatch - token may be stale');
      }

      return data;
    }

    // Fallback: Return basic profile info from token
    // This is used when backend endpoint is not available
    const baseProfile = getBaseProfileFromGroups(claims);
    const permissions = getDefaultPermissionsForProfile(baseProfile);

    return {
      profileId: profileId || baseProfile,
      profileName: getProfileName(baseProfile),
      baseProfile,
      permissions,
      version: profileVersion,
      hash: permissionsHash,
    };
  } catch (error) {
    console.error('Error fetching permissions:', error);
    throw error;
  }
}

/**
 * Calculate SHA-256 hash of permissions.
 *
 * This is used to validate that permissions haven't been tampered with.
 *
 * @param permissions - List of permission codes
 * @returns Truncated hash (16 characters)
 */
export async function calculatePermissionsHash(permissions: string[]): Promise<string> {
  if (!permissions || permissions.length === 0) {
    return '';
  }

  const sorted = [...permissions].sort();
  const json = JSON.stringify(sorted);

  // Use Web Crypto API
  const encoder = new TextEncoder();
  const data = encoder.encode(json);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');

  return hashHex.slice(0, 16);
}

/**
 * Validate permissions against expected hash.
 *
 * @param permissions - List of permission codes
 * @param expectedHash - Expected hash from JWT token
 * @returns True if hash matches
 */
export async function validatePermissionsHash(
  permissions: string[],
  expectedHash: string
): Promise<boolean> {
  if (!expectedHash) {
    return true; // No hash to validate
  }

  const calculated = await calculatePermissionsHash(permissions);
  return calculated === expectedHash;
}

// =============================================================================
// Route to Permission Mapping
// =============================================================================

/**
 * Route to permission code mapping.
 *
 * This defines which permission is required for each route.
 * Keep in sync with backend route_permissions.
 */
export const ROUTE_PERMISSIONS: Record<string, string> = {
  '/ferramentas/ativos/dashboard': 'EST_R01',
  '/ferramentas/ativos/estoque': 'EST_R02',
  '/ferramentas/ativos/estoque/entrada': 'EST_R02',
  '/ferramentas/ativos/estoque/saida': 'EST_R02',
  '/ferramentas/ativos/movimentacoes': 'MOV_R01',
  '/estoque/movimentacoes/entrada': 'MOV_C01',
  '/estoque/movimentacoes/saida': 'MOV_C02',
  '/estoque/movimentacoes/transferencia': 'MOV_C03',
  '/expedicao': 'EXP_R01',
  '/expedicao/nova': 'EXP_C01',
  '/reversa': 'REV_R01',
  '/reversa/nova': 'REV_C01',
  '/inventario': 'INV_R01',
  '/inventario/novo': 'INV_C01',
  '/cadastros': 'CAD_R01',
  '/transportadoras': 'TRANSP_R01',
  '/fiscal': 'FISC_R01',
  '/academy': 'ACAD_R01',
  '/admin/usuarios': 'ADMIN_U01',
  '/admin/perfis': 'ADMIN_P01',
};

/**
 * Get the permission code required for a route.
 *
 * @param route - Route path
 * @returns Permission code or null if no permission required
 */
export function getRoutePermission(route: string): string | null {
  // Check exact match first
  if (route in ROUTE_PERMISSIONS) {
    return ROUTE_PERMISSIONS[route];
  }

  // Check prefix matches for dynamic routes
  for (const [pattern, code] of Object.entries(ROUTE_PERMISSIONS)) {
    if (route.startsWith(pattern)) {
      return code;
    }
  }

  return null;
}

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Decode JWT token without validation.
 *
 * Note: This only decodes the payload. The signature is
 * validated by Cognito/AgentCore, not here.
 */
function decodeJwt(token: string): Record<string, unknown> {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      throw new Error('Invalid token format');
    }

    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    console.error('Failed to decode JWT');
    return {};
  }
}

/**
 * Get profile ID from Cognito groups.
 */
function getProfileFromGroups(claims: Record<string, unknown>): string | null {
  const groups = claims['cognito:groups'] as string[] | undefined;
  if (!groups || groups.length === 0) {
    return null;
  }

  // Return first matching group as profile
  const groupToProfile: Record<string, string> = {
    Admins: 'admin',
    Logistica: 'logistica',
    Tecnicos: 'tecnico',
    Financeiro: 'financeiro',
  };

  for (const group of ['Admins', 'Logistica', 'Tecnicos', 'Financeiro']) {
    if (groups.includes(group)) {
      return groupToProfile[group];
    }
  }

  return null;
}

/**
 * Get base profile from Cognito groups.
 */
function getBaseProfileFromGroups(claims: Record<string, unknown>): string {
  const profile = getProfileFromGroups(claims);
  return profile || 'guest';
}

/**
 * Get profile display name.
 */
function getProfileName(profileId: string): string {
  const names: Record<string, string> = {
    admin: 'Administrador',
    logistica: 'Logística',
    tecnico: 'Técnico',
    financeiro: 'Financeiro',
    guest: 'Visitante',
  };
  return names[profileId] || profileId;
}

/**
 * Get default permissions for a base profile.
 *
 * This is used as a fallback when the backend is not available.
 * In production, permissions should always come from the backend.
 */
function getDefaultPermissionsForProfile(profile: string): string[] {
  // Admin gets all permissions (represented by wildcard handling in checks)
  if (profile === 'admin') {
    return ['*'];
  }

  // Basic permissions by profile
  const profilePermissions: Record<string, string[]> = {
    logistica: [
      'AUTH_R01',
      'INTRA_R01',
      'NEXO_R01',
      'EST_R01',
      'EST_R02',
      'EST_R03',
      'MOV_R01',
      'MOV_C01',
      'MOV_C02',
      'MOV_C03',
      'EXP_R01',
      'EXP_C01',
      'REV_R01',
      'REV_C01',
      'TRANSP_R01',
    ],
    tecnico: [
      'AUTH_R01',
      'INTRA_R01',
      'NEXO_R01',
      'EST_R01',
      'EST_R02',
      'MOV_R01',
      'ACAD_R01',
    ],
    financeiro: [
      'AUTH_R01',
      'INTRA_R01',
      'NEXO_R01',
      'EST_R01',
      'FISC_R01',
      'ACAD_R01',
    ],
    guest: ['AUTH_R01'],
  };

  return profilePermissions[profile] || [];
}
