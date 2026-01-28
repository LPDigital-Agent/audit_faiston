/**
 * @file authService.ts
 * @description Serviço de autenticação usando AWS Cognito para o Faiston NEXO
 *
 * Este serviço encapsula todas as operações de autenticação:
 * - Sign Up (cadastro com verificação de email)
 * - Sign In (login com SRP - senha nunca enviada pela rede)
 * - Sign Out (local e global)
 * - Forgot/Reset Password
 * - Change Password
 * - Gerenciamento de sessão e tokens
 *
 * Segurança: Usa SRP (Secure Remote Password) - a senha nunca é transmitida
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  CognitoUserSession,
  ISignUpResult,
} from 'amazon-cognito-identity-js';
import { cognitoConfig } from '@/lib/config/cognito';

// =============================================================================
// Inicialização do User Pool (Lazy)
// =============================================================================
// Lazy initialization to prevent build errors during static export
// when environment variables are not available.

let _userPool: CognitoUserPool | null = null;

const getUserPool = (): CognitoUserPool => {
  if (!_userPool) {
    if (!cognitoConfig.userPoolId || !cognitoConfig.clientId) {
      throw new Error(
        'Configuração do Cognito incompleta. Verifique NEXT_PUBLIC_USER_POOL_ID e NEXT_PUBLIC_USER_POOL_CLIENT_ID.'
      );
    }
    _userPool = new CognitoUserPool({
      UserPoolId: cognitoConfig.userPoolId,
      ClientId: cognitoConfig.clientId,
    });
  }
  return _userPool;
};


// =============================================================================
// Tipos e Interfaces
// =============================================================================

/** Parâmetros para cadastro de novo usuário */
export interface SignUpParams {
  email: string;
  password: string;
  name?: string;
}

/** Parâmetros para login */
export interface SignInParams {
  email: string;
  password: string;
}

/** Tokens de autenticação */
export interface AuthTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
}

/** Atributos do usuário */
export interface UserAttributes {
  email: string;
  name?: string;
  sub: string; // Cognito user ID
}

/** Erro de New Password Required (admin-created users) */
export interface NewPasswordRequiredError {
  code: 'NewPasswordRequired';
  message: string;
  userAttributes: Record<string, string>;
  requiredAttributes: string[];
  cognitoUser: CognitoUser;
}

// =============================================================================
// SIGN UP (Cadastro)
// =============================================================================

/**
 * Cadastra um novo usuário no Cognito
 *
 * @param params - Email, senha e nome opcional
 * @returns Resultado do cadastro (requer confirmação de email)
 *
 * @example
 * ```typescript
 * const result = await signUp({
 *   email: 'usuario@faiston.com',
 *   password: 'Senha@123',
 *   name: 'João Silva'
 * });
 * // Usuário precisa confirmar email com código
 * ```
 */
export const signUp = (params: SignUpParams): Promise<ISignUpResult> => {
  return new Promise((resolve, reject) => {
    const { email, password, name } = params;

    const attributeList: CognitoUserAttribute[] = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
    ];

    if (name) {
      attributeList.push(
        new CognitoUserAttribute({ Name: 'name', Value: name })
      );
    }

    getUserPool().signUp(
      email, // username = email
      password,
      attributeList,
      [], // validation data
      (err, result) => {
        if (err) {
          reject(err);
          return;
        }
        if (!result) {
          reject(new Error('Falha no cadastro - nenhum resultado retornado'));
          return;
        }
        resolve(result);
      }
    );
  });
};

// =============================================================================
// CONFIRM SIGN UP (Verificação de Email)
// =============================================================================

/**
 * Confirma o cadastro com código de verificação enviado por email
 *
 * @param email - Email do usuário
 * @param code - Código de 6 dígitos recebido por email
 * @returns String de confirmação
 */
export const confirmSignUp = (
  email: string,
  code: string
): Promise<string> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: getUserPool(),
    });

    cognitoUser.confirmRegistration(code, true, (err, result) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(result);
    });
  });
};

// =============================================================================
// RESEND VERIFICATION CODE
// =============================================================================

/**
 * Reenvia o código de verificação de email
 *
 * @param email - Email do usuário
 */
export const resendVerificationCode = (email: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: getUserPool(),
    });

    cognitoUser.resendConfirmationCode((err) => {
      if (err) {
        reject(err);
        return;
      }
      resolve();
    });
  });
};

// =============================================================================
// SIGN IN (Login)
// =============================================================================

/**
 * Autentica o usuário com email e senha
 * Usa SRP (Secure Remote Password) - senha nunca enviada pela rede
 *
 * @param params - Email e senha
 * @returns Sessão do usuário com tokens
 * @throws {NewPasswordRequiredError} Se for usuário criado por admin que precisa definir nova senha
 */
export const signIn = (params: SignInParams): Promise<CognitoUserSession> => {
  return new Promise((resolve, reject) => {
    const { email, password } = params;

    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: getUserPool(),
    });

    const authenticationDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    });

    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: (session) => {
        resolve(session);
      },
      onFailure: (err) => {
        reject(err);
      },
      // Handle new password required (usuários criados por admin)
      newPasswordRequired: (userAttributes, requiredAttributes) => {
        // Remove atributos não modificáveis
        delete userAttributes.email_verified;
        delete userAttributes.email;

        reject({
          code: 'NewPasswordRequired',
          message: 'Nova senha necessária',
          userAttributes,
          requiredAttributes,
          cognitoUser,
        } as NewPasswordRequiredError);
      },
    });
  });
};

// =============================================================================
// COMPLETE NEW PASSWORD CHALLENGE
// =============================================================================

/**
 * Completa o desafio de nova senha (para usuários criados por admin)
 *
 * @param cognitoUser - Objeto CognitoUser do erro NewPasswordRequired
 * @param newPassword - Nova senha a ser definida
 * @param userAttributes - Atributos adicionais (opcional)
 */
export const completeNewPasswordChallenge = (
  cognitoUser: CognitoUser,
  newPassword: string,
  userAttributes: Record<string, string> = {}
): Promise<CognitoUserSession> => {
  return new Promise((resolve, reject) => {
    cognitoUser.completeNewPasswordChallenge(newPassword, userAttributes, {
      onSuccess: (session) => {
        resolve(session);
      },
      onFailure: (err) => {
        reject(err);
      },
    });
  });
};

// =============================================================================
// SIGN OUT
// =============================================================================

/**
 * Realiza logout local (apenas neste dispositivo)
 * Limpa tokens do localStorage
 */
export const signOut = (): void => {
  const cognitoUser = getUserPool().getCurrentUser();
  if (cognitoUser) {
    cognitoUser.signOut();
  }
};

/**
 * Realiza logout global (invalida todas as sessões)
 * Útil quando o usuário quer deslogar de todos os dispositivos
 */
export const globalSignOut = (): Promise<void> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = getUserPool().getCurrentUser();
    if (!cognitoUser) {
      resolve();
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) {
        signOut();
        resolve();
        return;
      }

      cognitoUser.globalSignOut({
        onSuccess: () => {
          resolve();
        },
        onFailure: (err) => {
          reject(err);
        },
      });
    });
  });
};

// =============================================================================
// FORGOT PASSWORD
// =============================================================================

/**
 * Inicia o fluxo de recuperação de senha
 * Envia código de verificação para o email do usuário
 *
 * @param email - Email do usuário
 */
export const forgotPassword = (email: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: getUserPool(),
    });

    cognitoUser.forgotPassword({
      onSuccess: () => {
        resolve();
      },
      onFailure: (err) => {
        reject(err);
      },
    });
  });
};

// =============================================================================
// CONFIRM FORGOT PASSWORD (Reset Password)
// =============================================================================

/**
 * Confirma a redefinição de senha com código e nova senha
 *
 * @param email - Email do usuário
 * @param code - Código de verificação recebido por email
 * @param newPassword - Nova senha
 */
export const confirmForgotPassword = (
  email: string,
  code: string,
  newPassword: string
): Promise<void> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: getUserPool(),
    });

    cognitoUser.confirmPassword(code, newPassword, {
      onSuccess: () => {
        resolve();
      },
      onFailure: (err) => {
        reject(err);
      },
    });
  });
};

// =============================================================================
// CHANGE PASSWORD (Usuário Autenticado)
// =============================================================================

/**
 * Altera a senha do usuário autenticado
 *
 * @param oldPassword - Senha atual
 * @param newPassword - Nova senha
 */
export const changePassword = (
  oldPassword: string,
  newPassword: string
): Promise<void> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = getUserPool().getCurrentUser();
    if (!cognitoUser) {
      reject(new Error('Nenhum usuário autenticado'));
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) {
        reject(err || new Error('Sessão inválida'));
        return;
      }

      cognitoUser.changePassword(oldPassword, newPassword, (err) => {
        if (err) {
          reject(err);
          return;
        }
        resolve();
      });
    });
  });
};

// =============================================================================
// GET CURRENT USER
// =============================================================================

/**
 * Retorna o usuário Cognito atual ou null se não autenticado
 */
export const getCurrentUser = (): CognitoUser | null => {
  return getUserPool().getCurrentUser();
};

// =============================================================================
// GET CURRENT SESSION
// =============================================================================

/**
 * Retorna a sessão atual do usuário
 *
 * @returns Sessão com tokens ou null se não autenticado
 */
export const getCurrentSession = (): Promise<CognitoUserSession | null> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = getUserPool().getCurrentUser();
    if (!cognitoUser) {
      resolve(null);
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(session);
    });
  });
};

// =============================================================================
// GET TOKENS
// =============================================================================

/**
 * Retorna os tokens JWT do usuário autenticado
 *
 * @returns Objeto com accessToken, idToken e refreshToken
 */
export const getTokens = async (): Promise<AuthTokens | null> => {
  const session = await getCurrentSession();
  if (!session) {
    return null;
  }

  return {
    accessToken: session.getAccessToken().getJwtToken(),
    idToken: session.getIdToken().getJwtToken(),
    refreshToken: session.getRefreshToken().getToken(),
  };
};

/**
 * Retorna apenas o ID Token (usado para chamadas GraphQL/AppSync)
 */
export const getIdToken = async (): Promise<string | null> => {
  const tokens = await getTokens();
  return tokens?.idToken || null;
};

/**
 * Retorna apenas o Access Token
 */
export const getAccessToken = async (): Promise<string | null> => {
  const tokens = await getTokens();
  return tokens?.accessToken || null;
};

// =============================================================================
// GET USER ATTRIBUTES
// =============================================================================

/**
 * Retorna os atributos do usuário atual (email, name, sub)
 */
export const getUserAttributes = (): Promise<UserAttributes | null> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = getUserPool().getCurrentUser();
    if (!cognitoUser) {
      resolve(null);
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) {
        resolve(null);
        return;
      }

      cognitoUser.getUserAttributes((err, attributes) => {
        if (err) {
          reject(err);
          return;
        }

        if (!attributes) {
          resolve(null);
          return;
        }

        const userAttrs: UserAttributes = {
          email: '',
          sub: '',
        };

        attributes.forEach((attr) => {
          if (attr.Name === 'email') userAttrs.email = attr.Value;
          if (attr.Name === 'name') userAttrs.name = attr.Value;
          if (attr.Name === 'sub') userAttrs.sub = attr.Value;
        });

        resolve(userAttrs);
      });
    });
  });
};

// =============================================================================
// CHECK IF AUTHENTICATED
// =============================================================================

/**
 * Verifica se o usuário está autenticado com sessão válida
 *
 * @returns true se autenticado e sessão válida
 */
export const isAuthenticated = async (): Promise<boolean> => {
  try {
    const session = await getCurrentSession();
    return session !== null && session.isValid();
  } catch {
    return false;
  }
};

// =============================================================================
// REFRESH SESSION
// =============================================================================

/**
 * Renova a sessão usando o refresh token
 *
 * @returns Nova sessão com tokens atualizados
 */
export const refreshSession = (): Promise<CognitoUserSession> => {
  return new Promise((resolve, reject) => {
    const cognitoUser = getUserPool().getCurrentUser();
    if (!cognitoUser) {
      reject(new Error('Nenhum usuário autenticado'));
      return;
    }

    cognitoUser.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session) {
        reject(err || new Error('Sessão inválida'));
        return;
      }

      const refreshToken = session.getRefreshToken();

      cognitoUser.refreshSession(refreshToken, (err, newSession) => {
        if (err) {
          reject(err);
          return;
        }
        resolve(newSession);
      });
    });
  });
};
