'use client';

/**
 * @file page.tsx
 * @description Página de Redefinição de Senha (com código + nova senha)
 */

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Lock, Eye, EyeOff, Check, X, CheckCircle, KeyRound } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';
import { validatePassword, passwordRequirements } from '@/lib/config/cognito';

// =============================================================================
// Componente de Requisitos de Senha
// =============================================================================

interface PasswordRequirementsProps {
  password: string;
}

function PasswordRequirements({ password }: PasswordRequirementsProps) {
  const checks = [
    {
      label: `Mínimo ${passwordRequirements.minLength} caracteres`,
      valid: password.length >= passwordRequirements.minLength,
    },
    {
      label: 'Uma letra maiúscula',
      valid: /[A-Z]/.test(password),
    },
    {
      label: 'Uma letra minúscula',
      valid: /[a-z]/.test(password),
    },
    {
      label: 'Um número',
      valid: /[0-9]/.test(password),
    },
    {
      label: 'Um caractere especial',
      valid: /[^A-Za-z0-9]/.test(password),
    },
  ];

  if (password.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      className="mt-2 p-3 rounded-lg bg-faiston-bg-glass border border-border"
    >
      <p className="text-xs text-text-muted mb-2">Requisitos da senha:</p>
      <ul className="space-y-1">
        {checks.map((check, index) => (
          <li
            key={index}
            className={`flex items-center gap-2 text-xs ${
              check.valid ? 'text-accent-success' : 'text-text-muted'
            }`}
          >
            {check.valid ? (
              <Check className="w-3 h-3" />
            ) : (
              <X className="w-3 h-3" />
            )}
            {check.label}
          </li>
        ))}
      </ul>
    </motion.div>
  );
}

// =============================================================================
// Loading Fallback
// =============================================================================

function LoadingFallback() {
  return (
    <AuthLayout title="Redefinir senha" subtitle="Carregando...">
      <div className="flex justify-center py-8">
        <Loader2 className="w-8 h-8 animate-spin text-accent-primary" />
      </div>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Interno (usa useSearchParams)
// =============================================================================

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { confirmForgotPassword } = useAuth();

  const email = searchParams.get('email') || '';

  // Form state
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Validação
  const passwordValidation = validatePassword(password);
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;
  const canSubmit =
    code.length === 6 &&
    passwordValidation.isValid &&
    password === confirmPassword &&
    !isLoading &&
    email;

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email) {
      setError('Email não encontrado. Por favor, volte e tente novamente.');
      return;
    }

    if (code.length !== 6) {
      setError('Por favor, insira o código de 6 dígitos.');
      return;
    }

    const pwdValidation = validatePassword(password);
    if (!pwdValidation.isValid) {
      setError(pwdValidation.errorMessage || 'Senha inválida');
      return;
    }

    if (password !== confirmPassword) {
      setError('As senhas não coincidem.');
      return;
    }

    setIsLoading(true);

    try {
      await confirmForgotPassword(email, code, password);
      setSuccess(true);

      // Redirecionar para login após 2 segundos
      setTimeout(() => {
        router.push('/login');
      }, 2000);
    } catch (err) {
      const authError = handleAuthError(err, email);
      setError(authError.userMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================================================
  // Render - Sucesso
  // ==========================================================================

  if (success) {
    return (
      <AuthLayout
        title="Senha alterada!"
        subtitle="Sua senha foi redefinida com sucesso."
      >
        <div className="flex flex-col items-center gap-4 py-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', damping: 10 }}
          >
            <CheckCircle className="w-16 h-16 text-accent-success" />
          </motion.div>
          <p className="text-text-secondary text-center">
            Redirecionando para o login...
          </p>
          <Loader2 className="w-5 h-5 animate-spin text-text-muted" />
        </div>
      </AuthLayout>
    );
  }

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <AuthLayout
      title="Redefinir senha"
      subtitle={email ? `Digite o código enviado para ${email}` : 'Digite o código e sua nova senha'}
    >
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

        {/* Ícone */}
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-full bg-accent-primary/10 flex items-center justify-center">
            <KeyRound className="w-8 h-8 text-accent-primary" />
          </div>
        </div>

        {/* Campo Código */}
        <div className="space-y-2">
          <label
            htmlFor="code"
            className="text-sm font-medium text-text-secondary"
          >
            Código de verificação
          </label>
          <Input
            id="code"
            type="text"
            inputMode="numeric"
            placeholder="000000"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            className="bg-faiston-bg-glass border-border text-center text-lg tracking-widest"
            disabled={isLoading}
            autoComplete="one-time-code"
            autoFocus
          />
        </div>

        {/* Campo Nova Senha */}
        <div className="space-y-2">
          <label
            htmlFor="password"
            className="text-sm font-medium text-text-secondary"
          >
            Nova senha
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
          <PasswordRequirements password={password} />
        </div>

        {/* Campo Confirmar Senha */}
        <div className="space-y-2">
          <label
            htmlFor="confirmPassword"
            className="text-sm font-medium text-text-secondary"
          >
            Confirmar nova senha
          </label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              id="confirmPassword"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={`pl-10 bg-faiston-bg-glass border-border ${
                !passwordsMatch ? 'border-accent-warning focus-visible:ring-accent-warning' : ''
              }`}
              disabled={isLoading}
              autoComplete="new-password"
            />
          </div>
          {!passwordsMatch && (
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
              Redefinindo...
            </>
          ) : (
            'Redefinir senha'
          )}
        </Button>

        {/* Links */}
        <div className="text-center pt-4 border-t border-border space-y-2">
          <Link
            href="/forgot-password"
            className="text-sm text-text-secondary hover:text-text-primary block"
          >
            Não recebeu o código? Tentar novamente
          </Link>
          <Link
            href="/login"
            className="text-sm text-accent-primary hover:underline"
          >
            ← Voltar para o login
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Principal (com Suspense)
// =============================================================================

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ResetPasswordContent />
    </Suspense>
  );
}
