'use client';

/**
 * @file ProtectedRoute.tsx
 * @description Componente para proteger rotas que requerem autenticação
 *
 * Verifica se o usuário está autenticado e redireciona para login se não estiver.
 * Mostra loading enquanto verifica o estado de autenticação.
 */

import { type ReactNode, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { FaistonIcon } from '@/components/shared/faiston-logo';

// =============================================================================
// Tipos
// =============================================================================

interface ProtectedRouteProps {
  /** Conteúdo a ser exibido se autenticado */
  children: ReactNode;

  /** Rota de redirecionamento se não autenticado (default: /login) */
  redirectTo?: string;

  /** Requer que o usuário seja admin */
  requireAdmin?: boolean;

  /** Componente customizado de loading */
  loadingComponent?: ReactNode;
}

// =============================================================================
// Componente de Loading Padrão
// =============================================================================

function DefaultLoadingScreen() {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-faiston-bg">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="flex flex-col items-center gap-4"
      >
        {/* Logo animado */}
        <motion.div
          animate={{
            scale: [1, 1.1, 1],
          }}
          transition={{
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        >
          <FaistonIcon size="lg" />
        </motion.div>

        {/* Spinner */}
        <div className="flex items-center gap-2 text-text-secondary">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Verificando autenticação...</span>
        </div>
      </motion.div>
    </div>
  );
}

// =============================================================================
// Componente Principal
// =============================================================================

/**
 * Protege rotas que requerem autenticação
 *
 * @example
 * ```tsx
 * // Proteger uma página
 * export default function DashboardPage() {
 *   return (
 *     <ProtectedRoute>
 *       <Dashboard />
 *     </ProtectedRoute>
 *   );
 * }
 *
 * // Requer admin
 * export default function AdminPage() {
 *   return (
 *     <ProtectedRoute requireAdmin>
 *       <AdminPanel />
 *     </ProtectedRoute>
 *   );
 * }
 * ```
 */
export function ProtectedRoute({
  children,
  redirectTo = '/login',
  requireAdmin = false,
  loadingComponent,
}: ProtectedRouteProps) {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  useEffect(() => {
    // Não fazer nada enquanto carrega
    if (isLoading) {
      return;
    }

    // Se não autenticado, redirecionar para login
    if (!isAuthenticated) {
      // Salvar a URL atual para retornar após login
      const currentPath = window.location.pathname;
      const returnUrl = currentPath !== '/' ? `?returnUrl=${encodeURIComponent(currentPath)}` : '';

      router.push(`${redirectTo}${returnUrl}`);
      return;
    }

    // Se requer admin mas usuário não é admin
    // TODO: Implementar verificação de admin quando tivermos o campo no user
    // if (requireAdmin && !user?.isAdmin) {
    //   router.push('/unauthorized');
    //   return;
    // }
  }, [isAuthenticated, isLoading, router, redirectTo, requireAdmin, user]);

  // Mostrar loading enquanto verifica autenticação
  if (isLoading) {
    return loadingComponent || <DefaultLoadingScreen />;
  }

  // Se não autenticado, não renderizar nada (vai redirecionar)
  if (!isAuthenticated) {
    return loadingComponent || <DefaultLoadingScreen />;
  }

  // Usuário autenticado, renderizar conteúdo
  return <>{children}</>;
}

export default ProtectedRoute;
