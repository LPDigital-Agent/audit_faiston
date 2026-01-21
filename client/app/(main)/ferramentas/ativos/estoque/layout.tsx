// =============================================================================
// Estoque Layout - SGA Inventory Module
// =============================================================================
// Pass-through layout for estoque routes.
// Context providers are now in the parent layout (/ferramentas/ativos/layout.tsx)
// to ensure ALL ativos routes have access to providers.
// =============================================================================

import { ReactNode } from 'react';

interface EstoqueLayoutProps {
  children: ReactNode;
}

export default function EstoqueLayout({ children }: EstoqueLayoutProps) {
  // Providers are in parent layout - just pass through children
  return <>{children}</>;
}
