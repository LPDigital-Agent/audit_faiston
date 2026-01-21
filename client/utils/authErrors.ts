/**
 * @file authErrors.ts
 * @description Utilitário para tratamento de erros de autenticação do Cognito
 *
 * Mapeia códigos de erro do AWS Cognito para mensagens amigáveis em português,
 * com ações sugeridas para cada tipo de erro.
 *
 * Segurança: Mensagens genéricas para evitar user enumeration
 */

// =============================================================================
// Tipos
// =============================================================================

/** Ação sugerida para o erro */
export type AuthErrorAction = 'redirect' | 'resend' | 'retry' | 'wait';

/** Estrutura padronizada de erro de autenticação */
export interface AuthError {
  /** Código original do Cognito */
  code: string;

  /** Mensagem original (para debug) */
  message: string;

  /** Mensagem amigável para exibir ao usuário (em português) */
  userMessage: string;

  /** Ação sugerida */
  action?: AuthErrorAction;

  /** Rota para redirecionamento (se action === 'redirect') */
  redirectTo?: string;
}

// =============================================================================
// Handler Principal
// =============================================================================

/**
 * Converte erro do Cognito para formato padronizado com mensagem amigável
 *
 * @param error - Erro recebido do Cognito
 * @param email - Email do usuário (opcional, usado para redirecionamentos)
 * @returns Objeto AuthError com mensagem em português
 *
 * @example
 * ```typescript
 * try {
 *   await signIn({ email, password });
 * } catch (err) {
 *   const authError = handleAuthError(err, email);
 *   setError(authError.userMessage);
 *
 *   if (authError.action === 'redirect' && authError.redirectTo) {
 *     navigate(authError.redirectTo);
 *   }
 * }
 * ```
 */
export const handleAuthError = (error: unknown, email?: string): AuthError => {
  // Extrai código do erro (pode vir em diferentes formatos)
  const err = error as { code?: string; name?: string; message?: string };
  const code = err.code || err.name || 'UnknownError';
  const message = err.message || 'Erro desconhecido';

  switch (code) {
    // =========================================================================
    // Erros de Cadastro
    // =========================================================================

    case 'UsernameExistsException':
      return {
        code,
        message,
        userMessage: 'Já existe uma conta com este email.',
        action: 'redirect',
        redirectTo: '/login',
      };

    case 'InvalidPasswordException':
      return {
        code,
        message,
        userMessage:
          'A senha deve ter pelo menos 8 caracteres, incluindo maiúscula, minúscula, número e caractere especial.',
        action: 'retry',
      };

    // =========================================================================
    // Erros de Verificação de Email
    // =========================================================================

    case 'UserNotConfirmedException':
      return {
        code,
        message,
        userMessage: 'Por favor, verifique seu email antes de fazer login.',
        action: 'redirect',
        redirectTo: '/confirm-signup',
      };

    case 'CodeMismatchException':
      return {
        code,
        message,
        userMessage: 'Código de verificação inválido. Por favor, tente novamente.',
        action: 'retry',
      };

    case 'ExpiredCodeException':
      return {
        code,
        message,
        userMessage: 'Este código expirou. Por favor, solicite um novo código.',
        action: 'resend',
      };

    case 'AliasExistsException':
      return {
        code,
        message,
        userMessage: 'Este email já está verificado em outra conta.',
        action: 'redirect',
        redirectTo: '/login',
      };

    // =========================================================================
    // Erros de Login
    // =========================================================================

    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      // IMPORTANTE: Mensagem genérica para prevenir user enumeration
      // Não revelamos se o email existe ou não
      return {
        code,
        message,
        userMessage: 'Email ou senha incorretos.',
        action: 'retry',
      };

    case 'NewPasswordRequired':
      return {
        code,
        message,
        userMessage: 'Você precisa definir uma nova senha.',
        action: 'redirect',
        redirectTo: '/new-password',
      };

    case 'PasswordResetRequiredException':
      return {
        code,
        message,
        userMessage: 'Sua senha precisa ser redefinida. Por favor, use "Esqueci minha senha".',
        action: 'redirect',
        redirectTo: '/forgot-password',
      };

    case 'UserDisabledException':
      return {
        code,
        message,
        userMessage: 'Esta conta foi desativada. Entre em contato com o suporte.',
        action: 'retry',
      };

    // =========================================================================
    // Erros de Rate Limiting
    // =========================================================================

    case 'LimitExceededException':
    case 'TooManyRequestsException':
      return {
        code,
        message,
        userMessage: 'Muitas tentativas. Por favor, aguarde alguns minutos e tente novamente.',
        action: 'wait',
      };

    case 'TooManyFailedAttemptsException':
      return {
        code,
        message,
        userMessage: 'Conta temporariamente bloqueada por muitas tentativas incorretas. Tente novamente mais tarde.',
        action: 'wait',
      };

    // =========================================================================
    // Erros de Parâmetros
    // =========================================================================

    case 'InvalidParameterException':
      return {
        code,
        message,
        userMessage: 'Dados inválidos. Por favor, verifique as informações e tente novamente.',
        action: 'retry',
      };

    case 'InvalidEmailRoleAccessPolicyException':
      return {
        code,
        message,
        userMessage: 'Não foi possível enviar o email. Tente novamente mais tarde.',
        action: 'retry',
      };

    // =========================================================================
    // Erros de Rede/Conexão
    // =========================================================================

    case 'NetworkError':
      return {
        code,
        message,
        userMessage: 'Erro de conexão. Verifique sua internet e tente novamente.',
        action: 'retry',
      };

    // =========================================================================
    // Erro Padrão
    // =========================================================================

    default:
      return {
        code,
        message,
        userMessage: 'Ocorreu um erro inesperado. Por favor, tente novamente.',
        action: 'retry',
      };
  }
};

// =============================================================================
// Helpers
// =============================================================================

/**
 * Verifica se o erro é de autenticação (credenciais inválidas)
 */
export const isAuthenticationError = (code: string): boolean => {
  return ['NotAuthorizedException', 'UserNotFoundException'].includes(code);
};

/**
 * Verifica se o erro requer verificação de email
 */
export const requiresEmailVerification = (code: string): boolean => {
  return code === 'UserNotConfirmedException';
};

/**
 * Verifica se o erro é de rate limiting
 */
export const isRateLimitError = (code: string): boolean => {
  return [
    'LimitExceededException',
    'TooManyRequestsException',
    'TooManyFailedAttemptsException',
  ].includes(code);
};

/**
 * Verifica se o erro é de código expirado/inválido
 */
export const isCodeError = (code: string): boolean => {
  return ['CodeMismatchException', 'ExpiredCodeException'].includes(code);
};
