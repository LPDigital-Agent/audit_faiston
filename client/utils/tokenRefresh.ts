/**
 * @file tokenRefresh.ts
 * @description Utilitário para gerenciamento automático de refresh de tokens
 *
 * Garante que os tokens JWT estejam sempre válidos, renovando-os
 * automaticamente antes de expirarem.
 */

import { refreshSession, getTokens, signOut } from '@/services/authService';
import { tokenConfig } from '@/lib/config/cognito';

// =============================================================================
// Tipos
// =============================================================================

interface TokenPayload {
  exp: number;
  iat: number;
  sub: string;
  [key: string]: unknown;
}

// =============================================================================
// Funções de Decodificação
// =============================================================================

/**
 * Decodifica o payload de um JWT (sem verificar assinatura)
 * Usado apenas para verificar expiração
 *
 * @param token - Token JWT
 * @returns Payload decodificado
 */
const decodeToken = (token: string): TokenPayload | null => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return null;
    }

    const payload = parts[1];
    // Base64 URL decode
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
};

/**
 * Verifica se um token está próximo de expirar
 *
 * @param token - Token JWT
 * @param marginMinutes - Margem de segurança em minutos (default: 5)
 * @returns true se o token expira dentro da margem
 */
export const isTokenExpiringSoon = (
  token: string,
  marginMinutes: number = tokenConfig.refreshMargin
): boolean => {
  const payload = decodeToken(token);
  if (!payload) {
    return true; // Token inválido, considerar como expirado
  }

  const expiresAt = payload.exp * 1000; // Converter para milliseconds
  const now = Date.now();
  const marginMs = marginMinutes * 60 * 1000;

  return expiresAt - now < marginMs;
};

/**
 * Verifica se um token já expirou
 *
 * @param token - Token JWT
 * @returns true se o token já expirou
 */
export const isTokenExpired = (token: string): boolean => {
  const payload = decodeToken(token);
  if (!payload) {
    return true;
  }

  const expiresAt = payload.exp * 1000;
  return Date.now() >= expiresAt;
};

/**
 * Retorna o tempo restante até a expiração do token em minutos
 *
 * @param token - Token JWT
 * @returns Minutos até expiração (0 se já expirou)
 */
export const getTokenTimeRemaining = (token: string): number => {
  const payload = decodeToken(token);
  if (!payload) {
    return 0;
  }

  const expiresAt = payload.exp * 1000;
  const remaining = expiresAt - Date.now();
  return Math.max(0, Math.floor(remaining / 60000));
};

// =============================================================================
// Função Principal de Refresh
// =============================================================================

/**
 * Garante que o ID Token esteja válido, renovando se necessário
 *
 * Esta função deve ser chamada antes de fazer requisições à API
 * para garantir que o token usado está válido.
 *
 * @returns ID Token válido ou null se não autenticado
 *
 * @example
 * ```typescript
 * const authLink = setContext(async (_, { headers }) => {
 *   const token = await ensureValidToken();
 *   if (!token) {
 *     // Redirecionar para login
 *     window.location.href = '/login';
 *     return { headers };
 *   }
 *   return {
 *     headers: {
 *       ...headers,
 *       authorization: token,
 *     },
 *   };
 * });
 * ```
 */
export const ensureValidToken = async (): Promise<string | null> => {
  try {
    const tokens = await getTokens();
    if (!tokens) {
      return null;
    }

    const { idToken } = tokens;

    // Verificar se o token está próximo de expirar
    if (!isTokenExpiringSoon(idToken)) {
      return idToken;
    }

    // Token está expirando, tentar renovar
    console.log('[Auth] Token expirando, iniciando refresh...');

    try {
      await refreshSession();
      const newTokens = await getTokens();

      if (newTokens?.idToken) {
        console.log('[Auth] Token renovado com sucesso');
        return newTokens.idToken;
      }
    } catch (refreshError) {
      console.error('[Auth] Falha ao renovar token:', refreshError);
      // Se não conseguir renovar, fazer logout
      signOut();
      return null;
    }

    return null;
  } catch (error) {
    console.error('[Auth] Erro ao verificar token:', error);
    return null;
  }
};

// =============================================================================
// Refresh Automático (Opcional)
// =============================================================================

let refreshInterval: NodeJS.Timeout | null = null;

/**
 * Inicia o refresh automático de tokens em background
 *
 * Verifica periodicamente se o token está expirando e renova automaticamente.
 * Útil para sessões longas onde o usuário fica inativo.
 *
 * @param intervalMinutes - Intervalo de verificação em minutos (default: 5)
 */
export const startAutoRefresh = (intervalMinutes: number = 5): void => {
  if (refreshInterval) {
    return; // Já está rodando
  }

  const intervalMs = intervalMinutes * 60 * 1000;

  refreshInterval = setInterval(async () => {
    const token = await ensureValidToken();
    if (!token) {
      // Não conseguiu renovar, parar auto-refresh
      stopAutoRefresh();
    }
  }, intervalMs);

  console.log(`[Auth] Auto-refresh iniciado (intervalo: ${intervalMinutes}min)`);
};

/**
 * Para o refresh automático de tokens
 */
export const stopAutoRefresh = (): void => {
  if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
    console.log('[Auth] Auto-refresh parado');
  }
};

/**
 * Verifica se o auto-refresh está ativo
 */
export const isAutoRefreshRunning = (): boolean => {
  return refreshInterval !== null;
};

// =============================================================================
// Access Token Validation (AgentCore)
// =============================================================================

/**
 * Garante que o Access Token esteja válido, renovando se necessário
 *
 * Esta função deve ser chamada antes de fazer requisições ao AWS Bedrock AgentCore
 * que requer accessToken (diferente de GraphQL que usa idToken).
 *
 * @returns Access Token válido ou null se não autenticado
 *
 * @example
 * ```typescript
 * const token = await ensureValidAccessToken();
 * if (!token) {
 *   // Redirecionar para login
 *   window.location.href = '/login';
 *   return;
 * }
 * // Usar token para AgentCore
 * headers: { Authorization: `Bearer ${token}` }
 * ```
 */
export const ensureValidAccessToken = async (): Promise<string | null> => {
  try {
    const tokens = await getTokens();
    if (!tokens) {
      return null;
    }

    const { accessToken } = tokens;

    // Verificar se o token está próximo de expirar
    if (!isTokenExpiringSoon(accessToken)) {
      return accessToken;
    }

    // Token está expirando, tentar renovar
    console.log('[Auth] Access Token expirando, iniciando refresh...');

    try {
      await refreshSession();
      const newTokens = await getTokens();

      if (newTokens?.accessToken) {
        console.log('[Auth] Access Token renovado com sucesso');
        return newTokens.accessToken;
      }
    } catch (refreshError) {
      console.error('[Auth] Falha ao renovar access token:', refreshError);
      // Se não conseguir renovar, fazer logout
      signOut();
      return null;
    }

    return null;
  } catch (error) {
    console.error('[Auth] Erro ao verificar access token:', error);
    return null;
  }
};
