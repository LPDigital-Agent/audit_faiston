'use client';

/**
 * @file page.tsx
 * @description Página de Esqueci Minha Senha
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Mail, KeyRound, CheckCircle } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';
import { validateEmail } from '@/lib/config/cognito';

// =============================================================================
// Componente
// =============================================================================

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { forgotPassword } = useAuth();

  // Form state
  const [email, setEmail] = useState('');

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Validação
  const isEmailValid = email.length === 0 || validateEmail(email);
  const canSubmit = validateEmail(email) && !isLoading;

  // ==========================================================================
  // Effects
  // ==========================================================================

  // Auto-redirect para reset-password após enviar código
  useEffect(() => {
    if (success && email) {
      const timer = setTimeout(() => {
        router.push(`/reset-password?email=${encodeURIComponent(email)}`);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [success, email, router]);

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
      await forgotPassword(email);
      setSuccess(true);
    } catch (err) {
      const authError = handleAuthError(err, email);

      // IMPORTANTE: Mensagem genérica para prevenir user enumeration
      // Mesmo se o email não existir, mostramos a mesma mensagem
      setSuccess(true);
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
        title="Verifique seu email"
        subtitle="Enviamos instruções para redefinir sua senha."
      >
        <div className="space-y-6">
          <div className="flex justify-center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', damping: 10 }}
              className="w-16 h-16 rounded-full bg-accent-success/10 flex items-center justify-center"
            >
              <CheckCircle className="w-8 h-8 text-accent-success" />
            </motion.div>
          </div>

          <p className="text-sm text-text-secondary text-center">
            Se existe uma conta com o email <strong className="text-text-primary">{email}</strong>,
            você receberá um código de verificação em breve.
          </p>

          <div className="flex items-center justify-center gap-2 text-text-muted">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">Redirecionando...</span>
          </div>

          <div className="text-center pt-4 border-t border-border">
            <p className="text-sm text-text-secondary">
              Não recebeu o email?{' '}
              <button
                onClick={() => setSuccess(false)}
                className="text-accent-primary hover:underline font-medium"
              >
                Tentar novamente
              </button>
            </p>
          </div>
        </div>
      </AuthLayout>
    );
  }

  // ==========================================================================
  // Render
  // ==========================================================================

  return (
    <AuthLayout
      title="Esqueceu a senha?"
      subtitle="Não se preocupe, vamos ajudá-lo a recuperar o acesso."
    >
      <form onSubmit={handleSubmit} className="space-y-6">
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

        {/* Instruções */}
        <p className="text-sm text-text-secondary text-center">
          Insira o email da sua conta e enviaremos um código para redefinir sua senha.
        </p>

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

        {/* Botão Submit */}
        <Button
          type="submit"
          className="w-full bg-gradient-to-r from-magenta-dark to-magenta-mid hover:from-magenta-mid hover:to-magenta-light text-white font-medium"
          disabled={!canSubmit}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Enviando...
            </>
          ) : (
            'Enviar código'
          )}
        </Button>

        {/* Link para login */}
        <div className="text-center pt-4 border-t border-border">
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
