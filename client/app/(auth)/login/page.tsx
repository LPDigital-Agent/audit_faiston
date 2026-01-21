'use client';

/**
 * @file page.tsx
 * @description Página de Login do Faiston NEXO
 */

import { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Mail, Lock, Eye, EyeOff } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';
import { validateEmail } from '@/lib/config/cognito';
import { saveNewPasswordChallenge } from '@/utils/newPasswordChallenge';
import type { NewPasswordRequiredError } from '@/services/authService';

// =============================================================================
// Loading Fallback
// =============================================================================

function LoadingFallback() {
  return (
    <AuthLayout title="Entrar" subtitle="Carregando...">
      <div className="flex justify-center py-8">
        <Loader2 className="w-8 h-8 animate-spin text-accent-primary" />
      </div>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Interno (usa useSearchParams)
// =============================================================================

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { signIn } = useAuth();

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validação
  const isEmailValid = email.length === 0 || validateEmail(email);
  const canSubmit = email.length > 0 && password.length > 0 && !isLoading;

  // URL de retorno após login
  const returnUrl = searchParams.get('returnUrl') || '/';

  // Mensagem de sucesso (ex: senha alterada, email verificado)
  const successMessage = searchParams.get('message');

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!validateEmail(email)) {
      setError('Por favor, insira um email válido.');
      return;
    }

    setIsLoading(true);

    try {
      await signIn({ email, password });

      // Redirecionar para a URL de retorno ou dashboard
      router.push(returnUrl);
    } catch (err) {
      // Verificar se é NewPasswordRequired (usuário criado por admin)
      const error = err as NewPasswordRequiredError;
      if (error.code === 'NewPasswordRequired' && error.cognitoUser) {
        // Salvar dados do challenge e redirecionar
        saveNewPasswordChallenge(email, error.userAttributes, error.cognitoUser);
        router.push('/new-password');
        return;
      }

      const authError = handleAuthError(err, email);

      // Verificar se precisa redirecionar
      if (authError.action === 'redirect' && authError.redirectTo) {
        // Se precisa confirmar email, passar o email como parâmetro
        if (authError.redirectTo === '/confirm-signup') {
          router.push(`/confirm-signup?email=${encodeURIComponent(email)}`);
          return;
        }
        router.push(authError.redirectTo);
        return;
      }

      setError(authError.userMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <AuthLayout
      title="Entrar"
      subtitle="Bem-vindo de volta! Acesse sua conta."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Mensagem de sucesso */}
        {successMessage && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-lg bg-accent-success/10 border border-accent-success/30"
          >
            <p className="text-sm text-accent-success">{successMessage}</p>
          </motion.div>
        )}

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

        {/* Campo Email */}
        <div className="space-y-2">
          <label
            htmlFor="email"
            className="text-sm font-medium text-text-secondary"
          >
            Email
          </label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              id="email"
              type="email"
              placeholder="seu.email@faiston.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`pl-10 bg-faiston-bg-glass border-border ${
                !isEmailValid ? 'border-accent-warning focus-visible:ring-accent-warning' : ''
              }`}
              disabled={isLoading}
              autoComplete="email"
              autoFocus
            />
          </div>
          {!isEmailValid && (
            <p className="text-xs text-accent-warning">
              Por favor, insira um email válido.
            </p>
          )}
        </div>

        {/* Campo Senha */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label
              htmlFor="password"
              className="text-sm font-medium text-text-secondary"
            >
              Senha
            </label>
            <Link
              href="/forgot-password"
              className="text-xs text-accent-primary hover:underline"
            >
              Esqueceu a senha?
            </Link>
          </div>
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
              autoComplete="current-password"
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
              Entrando...
            </>
          ) : (
            'Entrar'
          )}
        </Button>

        {/* Link para cadastro */}
        <div className="text-center pt-4 border-t border-border">
          <p className="text-sm text-text-secondary">
            Não tem uma conta?{' '}
            <Link
              href="/signup"
              className="text-accent-primary hover:underline font-medium"
            >
              Criar conta
            </Link>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Principal (com Suspense)
// =============================================================================

export default function LoginPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <LoginContent />
    </Suspense>
  );
}
