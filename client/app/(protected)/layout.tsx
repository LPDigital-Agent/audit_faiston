import { AppShell } from '@/components/layout/app-shell';

/**
 * Layout para páginas protegidas (requer autenticação)
 * Usa o AppShell com sidebar e header
 */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell>{children}</AppShell>;
}
