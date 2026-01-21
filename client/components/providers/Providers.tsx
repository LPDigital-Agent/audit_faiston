'use client';

/**
 * @file Providers.tsx
 * @description Componente que agrupa todos os providers da aplicação
 *
 * Este componente é necessário porque o layout root deve ser um server component,
 * mas os providers precisam ser client components.
 */

import { type ReactNode } from 'react';
import { ApolloProvider } from '@apollo/client/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { AuthProvider } from '@/contexts/AuthContext';
import { apolloClient } from '@/lib/apolloClient';

// =============================================================================
// Query Client
// =============================================================================

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutos
      refetchOnWindowFocus: false,
    },
  },
});

// =============================================================================
// Componente
// =============================================================================

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Agrupa todos os providers da aplicação
 *
 * Ordem dos providers (de fora para dentro):
 * 1. QueryClientProvider (TanStack Query)
 * 2. ApolloProvider (GraphQL)
 * 3. AuthProvider (Autenticação)
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <ApolloProvider client={apolloClient}>
        <AuthProvider>{children}</AuthProvider>
      </ApolloProvider>
    </QueryClientProvider>
  );
}

export default Providers;
