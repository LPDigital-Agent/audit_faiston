'use client';

/**
 * @file page.tsx
 * @description Página para definir nova senha (usuários criados por admin)
 *
 * Fluxo:
 * 1. Admin cria usuário no Cognito com senha temporária
 * 2. Usuário tenta fazer login
 * 3. Cognito retorna challenge NewPasswordRequired
 * 4. Login redireciona para esta página
 * 5. Usuário define nova senha
 * 6. Redirecionado para dashboard
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Lock, Eye, EyeOff, AlertCircle, CheckCircle2 } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { completeNewPasswordChallenge } from '@/services/authService';
import { handleAuthError } from '@/utils/authErrors';
import { passwordRequirements, validatePassword } from '@/lib/config/cognito';
import {
  getNewPasswordChallenge,
  clearNewPasswordChallenge,
} from '@/utils/newPasswordChallenge';
import type { CognitoUser } from 'amazon-cognito-identity-js';

// =============================================================================
// Componente
// =============================================================================

export default function NewPasswordPage() {
  const router = useRouter();

  // Challenge data
  const [email, setEmail] = useState<string>('');
  const [cognitoUser, setCognitoUser] = useState<CognitoUser | null>(null);
  const [isValidChallenge, setIsValidChallenge] = useState<boolean | null>(null);

  // Form state
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validação de senha
  const passwordValidation = validatePassword(password);
  const passwordsMatch = password === confirmPassword;
  const canSubmit =
    password.length > 0 &&
    confirmPassword.length > 0 &&
    passwordValidation.isValid &&
    passwordsMatch &&
    !isLoading &&
    cognitoUser !== null;

  // ==========================================================================
  // Effects
  // ==========================================================================

  // Carregar dados do challenge ao montar
  useEffect(() => {
    const { data, cognitoUser: user } = getNewPasswordChallenge();

    if (!data || !user) {
      setIsValidChallenge(false);
      return;
    }

    setEmail(data.email);
    setCognitoUser(user);
    setIsValidChallenge(true);
  }, []);

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!cognitoUser) {
      setError('Sessão expirada. Por favor, tente fazer login novamente.');
      return;
    }

    if (!passwordValidation.isValid) {
      setError('A senha não atende aos requisitos.');
      return;
    }

    if (!passwordsMatch) {
      setError('As senhas não coincidem.');
      return;
    }

    setIsLoading(true);

    try {
      await completeNewPasswordChallenge(cognitoUser, password);

      // Limpar dados do challenge
      clearNewPasswordChallenge();

      // Redirecionar para login com mensagem de sucesso
      router.push('/login?message=Senha definida com sucesso! Faça login com sua nova senha.');
    } catch (err) {
      const authError = handleAuthError(err, email);
      setError(authError.userMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================================================
  // Render - Estado inválido
  // ==========================================================================

  if (isValidChallenge === false) {
    return (
      <AuthLayout
        title="Sessão Expirada"
        subtitle="O link para definir nova senha expirou ou é inválido."
      >
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <AlertCircle className="w-16 h-16 text-accent-warning" />
          </div>
          <p className="text-text-secondary">
            Por favor, tente fazer login novamente. Se você foi criado por um
            administrador, você será redirecionado para definir uma nova senha.
          </p>
          <Button
            onClick={() => router.push('/login')}
            className="w-full bg-gradient-to-r from-magenta-dark to-magenta-mid hover:from-magenta-mid hover:to-magenta-light text-white"
          >
            Ir para Login
          </Button>
        </div>
      </AuthLayout>
    );
  }

  // ==========================================================================
  // Render - Loading
  // ==========================================================================

  if (isValidChallenge === null) {
    return (
      <AuthLayout title="Carregando..." subtitle="">
        <div className="flex justify-center py-8">
          <Loader2 className="w-8 h-8 animate-spin text-accent-primary" />
        </div>
      </AuthLayout>
    );
  }

  // ==========================================================================
  // Render - Formulário
  // ==========================================================================

  return (
    <AuthLayout
      title="Definir Nova Senha"
      subtitle={`Olá! Defina uma nova senha para sua conta ${email}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Mensagem informativa */}
        <div className="p-3 rounded-lg bg-accent-primary/10 border border-accent-primary/30">
          <p className="text-sm text-accent-primary">
            Sua conta foi criada por um administrador. Por segurança, você
            precisa definir uma nova senha.
          </p>
        </div>

        {/* Mensagem de erro */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-lg bg-accent-warning/10 border border-accent-warning/30"
          >
            <p className="text-sm text-accent-warning">{error}</p>
          </motion.div>
        )}

        {/* Campo Nova Senha */}
        <div className="space-y-2">
          <label
            htmlFor="password"
            className="text-sm font-medium text-text-secondary"
          >
            Nova Senha
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pl-10 pr-10 bg-faiston-bg-glass border-border"
              disabled={isLoading}
              autoComplete="new-password"
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
              tabIndex={-1}
            >
              {showPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>

          {/* Requisitos de senha */}
          {password.length > 0 && (
            <div className="space-y-1 pt-2">
              <PasswordRequirement
                met={passwordValidation.checks.minLength}
                text={`Mínimo ${passwordRequirements.minLength} caracteres`}
              />
              <PasswordRequirement
                met={passwordValidation.checks.hasUppercase}
                text="Uma letra maiúscula"
              />
              <PasswordRequirement
                met={passwordValidation.checks.hasLowercase}
                text="Uma letra minúscula"
              />
              <PasswordRequirement
                met={passwordValidation.checks.hasNumber}
                text="Um número"
              />
              <PasswordRequirement
                met={passwordValidation.checks.hasSpecial}
                text="Um caractere especial (!@#$%^&*)"
              />
            </div>
          )}
        </div>

        {/* Campo Confirmar Senha */}
        <div className="space-y-2">
          <label
            htmlFor="confirmPassword"
            className="text-sm font-medium text-text-secondary"
          >
            Confirmar Nova Senha
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              id="confirmPassword"
              type={showConfirmPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={`pl-10 pr-10 bg-faiston-bg-glass border-border ${
                confirmPassword.length > 0 && !passwordsMatch
                  ? 'border-accent-warning focus-visible:ring-accent-warning'
                  : ''
              }`}
              disabled={isLoading}
              autoComplete="new-password"
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
              tabIndex={-1}
            >
              {showConfirmPassword ? (
                <EyeOff className="w-4 h-4" />
              ) : (
                <Eye className="w-4 h-4" />
              )}
            </button>
          </div>
          {confirmPassword.length > 0 && !passwordsMatch && (
            <p className="text-xs text-accent-warning">
              As senhas não coincidem.
            </p>
          )}
        </div>

        {/* Botão Submit */}
        <Button
          type="submit"
          className="w-full bg-gradient-to-r from-magenta-dark to-magenta-mid hover:from-magenta-mid hover:to-magenta-light text-white font-medium"
          disabled={!canSubmit}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Definindo senha...
            </>
          ) : (
            'Definir Nova Senha'
          )}
        </Button>

        {/* Link para login */}
        <div className="text-center pt-4 border-t border-border">
          <p className="text-sm text-text-secondary">
            Lembrou sua senha?{' '}
            <Link
              href="/login"
              className="text-accent-primary hover:underline font-medium"
            >
              Voltar ao login
            </Link>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}

// =============================================================================
// Componentes Auxiliares
// =============================================================================

function PasswordRequirement({ met, text }: { met: boolean; text: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      {met ? (
        <CheckCircle2 className="w-3.5 h-3.5 text-accent-success" />
      ) : (
        <div className="w-3.5 h-3.5 rounded-full border border-text-muted" />
      )}
      <span className={met ? 'text-accent-success' : 'text-text-muted'}>
        {text}
      </span>
    </div>
  );
}
