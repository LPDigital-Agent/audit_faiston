'use client';

/**
 * @file AuthLayout.tsx
 * @description Layout para páginas de autenticação (login, signup, etc.)
 *
 * Design:
 * - Fundo escuro com gradiente sutil
 * - Logo Faiston centralizado no topo
 * - Card glassmorphism para o formulário
 * - Animações suaves com Framer Motion
 */

import { type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { FaistonLogo } from '@/components/shared/faiston-logo';

// =============================================================================
// Tipos
// =============================================================================

interface AuthLayoutProps {
  /** Conteúdo do formulário/card */
  children: ReactNode;

  /** Título da página (ex: "Entrar", "Criar conta") */
  title: string;

  /** Subtítulo opcional */
  subtitle?: string;

  /** Largura máxima do card (default: 400px) */
  maxWidth?: 'sm' | 'md' | 'lg';
}

// =============================================================================
// Constantes
// =============================================================================

const maxWidthClasses = {
  sm: 'max-w-sm', // 384px
  md: 'max-w-md', // 448px
  lg: 'max-w-lg', // 512px
};

// =============================================================================
// Animações
// =============================================================================

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
    },
  },
};

const logoVariants = {
  hidden: { opacity: 0, scale: 0.9 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: {
      duration: 0.5,
      ease: [0.25, 0.46, 0.45, 0.94] as const,
    },
  },
};

// =============================================================================
// Componente
// =============================================================================

/**
 * Layout para páginas de autenticação
 *
 * @example
 * ```tsx
 * <AuthLayout title="Entrar" subtitle="Bem-vindo de volta!">
 *   <LoginForm />
 * </AuthLayout>
 * ```
 */
export function AuthLayout({
  children,
  title,
  subtitle,
  maxWidth = 'md',
}: AuthLayoutProps) {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Background com gradiente sutil */}
      <div className="absolute inset-0 bg-faiston-bg">
        {/* Gradiente decorativo no canto superior direito */}
        <div
          className="absolute -top-40 -right-40 w-96 h-96 rounded-full opacity-20 blur-3xl"
          style={{
            background: 'linear-gradient(135deg, var(--faiston-magenta-dark) 0%, var(--faiston-blue-dark) 100%)',
          }}
        />

        {/* Gradiente decorativo no canto inferior esquerdo */}
        <div
          className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full opacity-15 blur-3xl"
          style={{
            background: 'linear-gradient(135deg, var(--faiston-blue-mid) 0%, var(--faiston-magenta-mid) 100%)',
          }}
        />
      </div>

      {/* Conteúdo */}
      <motion.div
        className={`relative z-10 w-full ${maxWidthClasses[maxWidth]}`}
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Logo */}
        <motion.div
          className="flex justify-center mb-8"
          variants={logoVariants}
        >
          <FaistonLogo variant="negative" size="lg" />
        </motion.div>

        {/* Card Glassmorphism */}
        <motion.div
          className="relative rounded-2xl p-8 backdrop-blur-xl"
          variants={itemVariants}
          style={{
            background: 'rgba(21, 23, 32, 0.8)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
          }}
        >
          {/* Header do Card */}
          <motion.div className="text-center mb-6" variants={itemVariants}>
            <h1 className="text-2xl font-semibold text-text-primary font-heading mb-2">
              {title}
            </h1>
            {subtitle && (
              <p className="text-text-secondary text-sm">
                {subtitle}
              </p>
            )}
          </motion.div>

          {/* Conteúdo (Formulário) */}
          <motion.div variants={itemVariants}>
            {children}
          </motion.div>
        </motion.div>

        {/* Footer */}
        <motion.div
          className="text-center mt-6 text-text-muted text-xs"
          variants={itemVariants}
        >
          <p>&copy; {new Date().getFullYear()} Faiston. Todos os direitos reservados.</p>
        </motion.div>
      </motion.div>
    </div>
  );
}

export default AuthLayout;
