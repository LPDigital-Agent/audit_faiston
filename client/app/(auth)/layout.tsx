/**
 * @file layout.tsx
 * @description Layout para páginas de autenticação (route group)
 *
 * Este layout NÃO inclui o AppShell (sidebar/header).
 * Todas as páginas dentro de (auth)/ usarão apenas o AuthLayout.
 */

import { type ReactNode } from 'react';

interface AuthGroupLayoutProps {
  children: ReactNode;
}

export default function AuthGroupLayout({ children }: AuthGroupLayoutProps) {
  return (
    <main className="min-h-screen bg-faiston-bg">
      {children}
    </main>
  );
}
