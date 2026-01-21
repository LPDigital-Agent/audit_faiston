'use client';

/**
 * @file page.tsx
 * @description Página para alterar senha (usuários autenticados)
 *
 * Esta página permite que usuários autenticados alterem sua senha.
 * Requer a senha atual para confirmar a identidade.
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Loader2,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  ArrowLeft,
  ShieldCheck,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';
import { passwordRequirements, validatePassword } from '@/lib/config/cognito';

// =============================================================================
// Componente
// =============================================================================

export default function ChangePasswordPage() {
  const router = useRouter();
  const { changePassword, user } = useAuth();

  // Form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Validação de senha
  const passwordValidation = validatePassword(newPassword);
  const passwordsMatch = newPassword === confirmPassword;
  const canSubmit =
    currentPassword.length > 0 &&
    newPassword.length > 0 &&
    confirmPassword.length > 0 &&
    passwordValidation.isValid &&
    passwordsMatch &&
    !isLoading;

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!passwordValidation.isValid) {
      setError('A nova senha não atende aos requisitos.');
      return;
    }

    if (!passwordsMatch) {
      setError('As senhas não coincidem.');
      return;
    }

    if (currentPassword === newPassword) {
      setError('A nova senha deve ser diferente da senha atual.');
      return;
    }

    setIsLoading(true);

    try {
      await changePassword(currentPassword, newPassword);

      // Limpar formulário
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');

      // Mostrar mensagem de sucesso
      setSuccess(true);
    } catch (err) {
      const authError = handleAuthError(err);
      setError(authError.userMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="w-full max-w-md"
      >
        {/* Card */}
        <div className="bg-faiston-bg-glass backdrop-blur-md rounded-2xl border border-border p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <div className="w-16 h-16 rounded-full bg-accent-primary/10 flex items-center justify-center">
                <ShieldCheck className="w-8 h-8 text-accent-primary" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-text-primary">
              Alterar Senha
            </h1>
            <p className="text-sm text-text-secondary mt-1">
              {user?.email || 'Atualize sua senha de acesso'}
            </p>
          </div>

          {/* Mensagem de sucesso */}
          {success && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="p-4 rounded-lg bg-accent-success/10 border border-accent-success/30 mb-6"
            >
              <div className="flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 text-accent-success flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-accent-success">
                    Senha alterada com sucesso!
                  </p>
                  <p className="text-xs text-accent-success/80 mt-1">
                    Sua nova senha já está ativa.
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Formulário */}
          <form onSubmit={handleSubmit} className="space-y-4">
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

            {/* Senha Atual */}
            <div className="space-y-2">
              <label
                htmlFor="currentPassword"
                className="text-sm font-medium text-text-secondary"
              >
                Senha Atual
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <Input
                  id="currentPassword"
                  type={showCurrentPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="pl-10 pr-10 bg-faiston-bg border-border"
                  disabled={isLoading}
                  autoComplete="current-password"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                  tabIndex={-1}
                >
                  {showCurrentPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Divisor */}
            <div className="relative py-2">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-faiston-bg-glass px-2 text-text-muted">
                  Nova senha
                </span>
              </div>
            </div>

            {/* Nova Senha */}
            <div className="space-y-2">
              <label
                htmlFor="newPassword"
                className="text-sm font-medium text-text-secondary"
              >
                Nova Senha
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <Input
                  id="newPassword"
                  type={showNewPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="pl-10 pr-10 bg-faiston-bg border-border"
                  disabled={isLoading}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary transition-colors"
                  tabIndex={-1}
                >
                  {showNewPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Requisitos de senha */}
              {newPassword.length > 0 && (
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

            {/* Confirmar Nova Senha */}
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
                  className={`pl-10 pr-10 bg-faiston-bg border-border ${
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

            {/* Botões */}
            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
                className="flex-1 border-border hover:bg-white/5"
                disabled={isLoading}
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Voltar
              </Button>
              <Button
                type="submit"
                className="flex-1 bg-gradient-to-r from-magenta-dark to-magenta-mid hover:from-magenta-mid hover:to-magenta-light text-white font-medium"
                disabled={!canSubmit}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Alterando...
                  </>
                ) : (
                  'Alterar Senha'
                )}
              </Button>
            </div>

            {/* Link esqueci senha */}
            <div className="text-center pt-4 border-t border-border">
              <p className="text-sm text-text-secondary">
                Esqueceu sua senha atual?{' '}
                <Link
                  href="/forgot-password"
                  className="text-accent-primary hover:underline font-medium"
                >
                  Redefinir senha
                </Link>
              </p>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
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
