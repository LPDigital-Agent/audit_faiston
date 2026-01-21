/**
 * @file newPasswordChallenge.ts
 * @description Utilitário para gerenciar o challenge de nova senha (NewPasswordRequired)
 *
 * Quando um usuário é criado por admin no Cognito, no primeiro login
 * ele recebe o challenge NewPasswordRequired. Este utilitário armazena
 * os dados necessários para completar o challenge na página /new-password.
 */

import type { CognitoUser } from 'amazon-cognito-identity-js';

// =============================================================================
// Constantes
// =============================================================================

const CHALLENGE_STORAGE_KEY = 'faiston_new_password_challenge';
const CHALLENGE_EXPIRY_MS = 5 * 60 * 1000; // 5 minutos

// =============================================================================
// Tipos
// =============================================================================

interface NewPasswordChallengeData {
  email: string;
  userAttributes: Record<string, string>;
  timestamp: number;
}

// Tipo para a variável global que armazena o CognitoUser
interface WindowWithCognitoUser extends Window {
  __cognitoUserForNewPassword?: CognitoUser;
}

// =============================================================================
// Funções
// =============================================================================

/**
 * Salva dados do challenge de nova senha
 *
 * @param email - Email do usuário
 * @param userAttributes - Atributos retornados pelo Cognito
 * @param cognitoUser - Objeto CognitoUser necessário para completar o challenge
 *
 * @example
 * ```typescript
 * // No login, quando receber NewPasswordRequired:
 * catch (err) {
 *   if (err.code === 'NewPasswordRequired') {
 *     saveNewPasswordChallenge(email, err.userAttributes, err.cognitoUser);
 *     router.push('/new-password');
 *   }
 * }
 * ```
 */
export function saveNewPasswordChallenge(
  email: string,
  userAttributes: Record<string, string>,
  cognitoUser: CognitoUser
): void {
  const data: NewPasswordChallengeData = {
    email,
    userAttributes,
    timestamp: Date.now(),
  };

  // Salvar dados serializáveis no sessionStorage
  sessionStorage.setItem(CHALLENGE_STORAGE_KEY, JSON.stringify(data));

  // Salvar CognitoUser em variável global (não pode ser serializado)
  (window as WindowWithCognitoUser).__cognitoUserForNewPassword = cognitoUser;
}

/**
 * Recupera dados do challenge de nova senha
 *
 * @returns Objeto com dados e cognitoUser, ou nulls se não existir/expirado
 */
export function getNewPasswordChallenge(): {
  data: NewPasswordChallengeData | null;
  cognitoUser: CognitoUser | null;
} {
  try {
    const stored = sessionStorage.getItem(CHALLENGE_STORAGE_KEY);
    if (!stored) {
      return { data: null, cognitoUser: null };
    }

    const data = JSON.parse(stored) as NewPasswordChallengeData;

    // Verificar se expirou
    if (Date.now() - data.timestamp > CHALLENGE_EXPIRY_MS) {
      clearNewPasswordChallenge();
      return { data: null, cognitoUser: null };
    }

    const cognitoUser =
      (window as WindowWithCognitoUser).__cognitoUserForNewPassword || null;

    return { data, cognitoUser };
  } catch {
    return { data: null, cognitoUser: null };
  }
}

/**
 * Limpa dados do challenge de nova senha
 */
export function clearNewPasswordChallenge(): void {
  sessionStorage.removeItem(CHALLENGE_STORAGE_KEY);
  delete (window as WindowWithCognitoUser).__cognitoUserForNewPassword;
}

/**
 * Verifica se existe um challenge de nova senha válido
 */
export function hasNewPasswordChallenge(): boolean {
  const { data, cognitoUser } = getNewPasswordChallenge();
  return data !== null && cognitoUser !== null;
}
