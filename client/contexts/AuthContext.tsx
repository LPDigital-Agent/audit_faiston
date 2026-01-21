'use client';

/**
 * @file AuthContext.tsx
 * @description Contexto de autenticação React para o Faiston NEXO
 *
 * Fornece estado de autenticação e métodos para toda a aplicação.
 * Usa o hook useAuth() para acessar o contexto.
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import {
  signUp as authSignUp,
  confirmSignUp as authConfirmSignUp,
  signIn as authSignIn,
  signOut as authSignOut,
  forgotPassword as authForgotPassword,
  confirmForgotPassword as authConfirmForgotPassword,
  changePassword as authChangePassword,
  getCurrentSession,
  getUserAttributes,
  isAuthenticated as checkIsAuthenticated,
  resendVerificationCode as authResendCode,
  type SignUpParams,
  type SignInParams,
  type UserAttributes,
} from '@/services/authService';
import { startAutoRefresh, stopAutoRefresh } from '@/utils/tokenRefresh';

// =============================================================================
// Tipos
// =============================================================================

/** Estado de autenticação */
interface AuthState {
  /** Usuário está autenticado */
  isAuthenticated: boolean;

  /** Carregando estado de autenticação (verificação inicial) */
  isLoading: boolean;

  /** Dados do usuário autenticado */
  user: UserAttributes | null;
}

/** Contexto de autenticação com métodos */
interface AuthContextType extends AuthState {
  /** Cadastrar novo usuário */
  signUp: (params: SignUpParams) => Promise<void>;

  /** Confirmar email com código */
  confirmSignUp: (email: string, code: string) => Promise<void>;

  /** Reenviar código de verificação */
  resendVerificationCode: (email: string) => Promise<void>;

  /** Fazer login */
  signIn: (params: SignInParams) => Promise<void>;

  /** Fazer logout */
  signOut: () => void;

  /** Solicitar reset de senha */
  forgotPassword: (email: string) => Promise<void>;

  /** Confirmar reset de senha */
  confirmForgotPassword: (email: string, code: string, newPassword: string) => Promise<void>;

  /** Alterar senha (usuário autenticado) */
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;

  /** Recarregar estado de autenticação */
  refreshAuth: () => Promise<void>;
}

// =============================================================================
// Contexto
// =============================================================================

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// =============================================================================
// Provider
// =============================================================================

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Provider de autenticação que envolve a aplicação
 *
 * @example
 * ```tsx
 * // app/layout.tsx
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <body>
 *         <AuthProvider>
 *           {children}
 *         </AuthProvider>
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    user: null,
  });

  // ===========================================================================
  // Verificação de Autenticação
  // ===========================================================================

  const checkAuthStatus = useCallback(async () => {
    try {
      const authenticated = await checkIsAuthenticated();

      if (authenticated) {
        const userAttrs = await getUserAttributes();
        setState({
          isAuthenticated: true,
          isLoading: false,
          user: userAttrs,
        });

        // Iniciar auto-refresh de tokens
        startAutoRefresh();
      } else {
        setState({
          isAuthenticated: false,
          isLoading: false,
          user: null,
        });
        stopAutoRefresh();
      }
    } catch (error) {
      console.error('[Auth] Erro ao verificar autenticação:', error);
      setState({
        isAuthenticated: false,
        isLoading: false,
        user: null,
      });
      stopAutoRefresh();
    }
  }, []);

  // Verificar autenticação ao montar o componente
  useEffect(() => {
    checkAuthStatus();

    // Cleanup: parar auto-refresh ao desmontar
    return () => {
      stopAutoRefresh();
    };
  }, [checkAuthStatus]);

  // ===========================================================================
  // Métodos de Autenticação
  // ===========================================================================

  /**
   * Cadastrar novo usuário
   * Após sucesso, redirecionar para /confirm-signup
   */
  const signUp = async (params: SignUpParams): Promise<void> => {
    await authSignUp(params);
    // Usuário precisa confirmar email antes de fazer login
  };

  /**
   * Confirmar email com código de verificação
   */
  const confirmSignUp = async (email: string, code: string): Promise<void> => {
    await authConfirmSignUp(email, code);
  };

  /**
   * Reenviar código de verificação de email
   */
  const resendVerificationCode = async (email: string): Promise<void> => {
    await authResendCode(email);
  };

  /**
   * Fazer login
   * Após sucesso, atualiza estado e inicia auto-refresh
   */
  const signIn = async (params: SignInParams): Promise<void> => {
    await authSignIn(params);
    const userAttrs = await getUserAttributes();

    setState({
      isAuthenticated: true,
      isLoading: false,
      user: userAttrs,
    });

    // Iniciar auto-refresh de tokens
    startAutoRefresh();
  };

  /**
   * Fazer logout
   * Limpa estado e para auto-refresh
   */
  const signOut = useCallback(() => {
    authSignOut();
    stopAutoRefresh();

    setState({
      isAuthenticated: false,
      isLoading: false,
      user: null,
    });
  }, []);

  /**
   * Solicitar reset de senha
   * Envia código de verificação para o email
   */
  const forgotPassword = async (email: string): Promise<void> => {
    await authForgotPassword(email);
  };

  /**
   * Confirmar reset de senha com código e nova senha
   */
  const confirmForgotPassword = async (
    email: string,
    code: string,
    newPassword: string
  ): Promise<void> => {
    await authConfirmForgotPassword(email, code, newPassword);
  };

  /**
   * Alterar senha do usuário autenticado
   */
  const changePassword = async (
    oldPassword: string,
    newPassword: string
  ): Promise<void> => {
    await authChangePassword(oldPassword, newPassword);
  };

  /**
   * Recarregar estado de autenticação
   */
  const refreshAuth = async (): Promise<void> => {
    await checkAuthStatus();
  };

  // ===========================================================================
  // Valor do Contexto
  // ===========================================================================

  const value: AuthContextType = {
    ...state,
    signUp,
    confirmSignUp,
    resendVerificationCode,
    signIn,
    signOut,
    forgotPassword,
    confirmForgotPassword,
    changePassword,
    refreshAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// =============================================================================
// Hook
// =============================================================================

/**
 * Hook para acessar o contexto de autenticação
 *
 * @returns Contexto de autenticação com estado e métodos
 * @throws Error se usado fora do AuthProvider
 *
 * @example
 * ```tsx
 * function ProfileButton() {
 *   const { user, isAuthenticated, signOut } = useAuth();
 *
 *   if (!isAuthenticated) {
 *     return <Link href="/login">Entrar</Link>;
 *   }
 *
 *   return (
 *     <div>
 *       <span>Olá, {user?.name}</span>
 *       <button onClick={signOut}>Sair</button>
 *     </div>
 *   );
 * }
 * ```
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useAuth deve ser usado dentro de um AuthProvider');
  }

  return context;
};
