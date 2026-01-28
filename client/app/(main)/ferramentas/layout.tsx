/**
 * FerramentasLayout - Layout wrapper for all tools/ferramentas pages
 *
 * Note: AppShell is provided by the parent (main)/layout.tsx
 * This layout simply passes children through. It exists to allow
 * for future ferramentas-specific wrapping if needed.
 *
 * Each tool (like Gestão de Ativos) can have its own nested layout
 * for module-specific navigation (tabs, headers, etc).
 */

interface FerramentasLayoutProps {
  children: React.ReactNode;
}

export default function FerramentasLayout({
  children,
}: FerramentasLayoutProps) {
  return <>{children}</>;
}
