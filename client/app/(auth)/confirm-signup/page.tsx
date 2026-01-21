'use client';

/**
 * @file page.tsx
 * @description Página de Confirmação de Email (código de verificação)
 */

import { useState, useRef, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Mail, RefreshCw, CheckCircle } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';

// =============================================================================
// Componente de Input de Código
// =============================================================================

interface CodeInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

function CodeInput({ value, onChange, disabled }: CodeInputProps) {
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const codeLength = 6;

  const handleChange = (index: number, digit: string) => {
    if (!/^\d*$/.test(digit)) return;

    const newValue = value.split('');
    newValue[index] = digit.slice(-1);
    const newCode = newValue.join('').slice(0, codeLength);
    onChange(newCode);

    // Auto-focus próximo input
    if (digit && index < codeLength - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !value[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, codeLength);
    onChange(pastedData);

    // Focus no último input preenchido
    const lastIndex = Math.min(pastedData.length - 1, codeLength - 1);
    inputRefs.current[lastIndex]?.focus();
  };

  return (
    <div className="flex gap-2 justify-center">
      {Array.from({ length: codeLength }).map((_, index) => (
        <Input
          key={index}
          ref={(el) => { inputRefs.current[index] = el; }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={value[index] || ''}
          onChange={(e) => handleChange(index, e.target.value)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          onPaste={handlePaste}
          disabled={disabled}
          className="w-12 h-14 text-center text-xl font-bold bg-faiston-bg-glass border-border focus:border-accent-primary"
          autoFocus={index === 0}
        />
      ))}
    </div>
  );
}

// =============================================================================
// Loading Fallback
// =============================================================================

function LoadingFallback() {
  return (
    <AuthLayout title="Verificar email" subtitle="Carregando...">
      <div className="flex justify-center py-8">
        <Loader2 className="w-8 h-8 animate-spin text-accent-primary" />
      </div>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Interno (usa useSearchParams)
// =============================================================================

function ConfirmSignUpContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { confirmSignUp, resendVerificationCode } = useAuth();

  const email = searchParams.get('email') || '';

  // Form state
  const [code, setCode] = useState('');

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  // Cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Validação
  const canSubmit = code.length === 6 && !isLoading && email;

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) {
      setError('Email não encontrado. Por favor, volte e tente novamente.');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await confirmSignUp(email, code);
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

  const handleResendCode = async () => {
    if (!email || isResending || resendCooldown > 0) return;

    setIsResending(true);
    setError(null);

    try {
      await resendVerificationCode(email);
      setResendCooldown(60); // 60 segundos de cooldown
    } catch (err) {
      const authError = handleAuthError(err, email);
      setError(authError.userMessage);
    } finally {
      setIsResending(false);
    }
  };

  // ==========================================================================
  // Render - Sucesso
  // ==========================================================================

  if (success) {
    return (
      <AuthLayout
        title="Email confirmado!"
        subtitle="Sua conta foi verificada com sucesso."
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
      title="Verificar email"
      subtitle={email ? `Enviamos um código para ${email}` : 'Insira o código de verificação'}
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
            <Mail className="w-8 h-8 text-accent-primary" />
          </div>
        </div>

        {/* Instruções */}
        <p className="text-sm text-text-secondary text-center">
          Digite o código de 6 dígitos que enviamos para o seu email.
        </p>

        {/* Input do código */}
        <CodeInput
          value={code}
          onChange={setCode}
          disabled={isLoading}
        />

        {/* Botão Submit */}
        <Button
          type="submit"
          className="w-full bg-gradient-to-r from-magenta-dark to-magenta-mid hover:from-magenta-mid hover:to-magenta-light text-white font-medium"
          disabled={!canSubmit}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Verificando...
            </>
          ) : (
            'Verificar'
          )}
        </Button>

        {/* Reenviar código */}
        <div className="text-center">
          <button
            type="button"
            onClick={handleResendCode}
            disabled={isResending || resendCooldown > 0}
            className="text-sm text-text-secondary hover:text-text-primary transition-colors inline-flex items-center gap-2 disabled:opacity-50"
          >
            {isResending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Reenviando...
              </>
            ) : resendCooldown > 0 ? (
              <>
                <RefreshCw className="w-4 h-4" />
                Reenviar em {resendCooldown}s
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Reenviar código
              </>
            )}
          </button>
        </div>

        {/* Link para voltar */}
        <div className="text-center pt-4 border-t border-border">
          <Link
            href="/signup"
            className="text-sm text-accent-primary hover:underline"
          >
            ← Voltar para o cadastro
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}

// =============================================================================
// Componente Principal (com Suspense)
// =============================================================================

export default function ConfirmSignUpPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ConfirmSignUpContent />
    </Suspense>
  );
}
