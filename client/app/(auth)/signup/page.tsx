'use client';

/**
 * @file page.tsx
 * @description Página de Cadastro (Sign Up) do Faiston NEXO
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Loader2, Mail, Lock, Eye, EyeOff, User, Check, X } from 'lucide-react';

import { AuthLayout } from '@/components/auth/AuthLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/contexts/AuthContext';
import { handleAuthError } from '@/utils/authErrors';
import { validateEmail, validatePassword, passwordRequirements } from '@/lib/config/cognito';

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
// Componente Principal
// =============================================================================

export default function SignUpPage() {
  const router = useRouter();
  const { signUp } = useAuth();

  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // UI state
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validação
  const isEmailValid = email.length === 0 || validateEmail(email);
  const passwordValidation = validatePassword(password);
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;
  const canSubmit =
    name.length > 0 &&
    validateEmail(email) &&
    passwordValidation.isValid &&
    password === confirmPassword &&
    !isLoading;

  // ==========================================================================
  // Handlers
  // ==========================================================================

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validações
    if (!validateEmail(email)) {
      setError('Por favor, insira um email válido.');
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
      await signUp({ email, password, name });

      // Redirecionar para confirmação de email
      router.push(`/confirm-signup?email=${encodeURIComponent(email)}`);
    } catch (err) {
      const authError = handleAuthError(err, email);

      // Verificar se precisa redirecionar
      if (authError.action === 'redirect' && authError.redirectTo) {
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
      title="Criar conta"
      subtitle="Junte-se à equipe Faiston!"
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

        {/* Campo Nome */}
        <div className="space-y-2">
          <label
            htmlFor="name"
            className="text-sm font-medium text-text-secondary"
          >
            Nome completo
          </label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <Input
              id="name"
              type="text"
              placeholder="Seu nome"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="pl-10 bg-faiston-bg-glass border-border"
              disabled={isLoading}
              autoComplete="name"
              autoFocus
            />
          </div>
        </div>

        {/* Campo Email */}
        <div className="space-y-2">
          <label
            htmlFor="email"
            className="text-sm font-medium text-text-secondary"
          >
            Email corporativo
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
            />
          </div>
          {!isEmailValid && (
            <p className="text-xs text-accent-warning">
              Domínio de email inválido
            </p>
          )}
        </div>

        {/* Campo Senha */}
        <div className="space-y-2">
          <label
            htmlFor="password"
            className="text-sm font-medium text-text-secondary"
          >
            Senha
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
            Confirmar senha
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
              Criando conta...
            </>
          ) : (
            'Criar conta'
          )}
        </Button>

        {/* Link para login */}
        <div className="text-center pt-4 border-t border-border">
          <p className="text-sm text-text-secondary">
            Já tem uma conta?{' '}
            <Link
              href="/login"
              className="text-accent-primary hover:underline font-medium"
            >
              Entrar
            </Link>
          </p>
        </div>
      </form>
    </AuthLayout>
  );
}
