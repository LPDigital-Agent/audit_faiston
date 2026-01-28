"use client";

import { Button } from "@/components/ui/button";
import { Plus, Download, Search } from "lucide-react";
import { GradientText } from "@/components/shared/gradient-text";
import Link from "next/link";

/**
 * AssetManagementHeader - Header component for Asset Management pages
 *
 * Features:
 * - Title with optional subtitle
 * - Primary action button (e.g., "Novo Ativo")
 * - Secondary actions (export, search)
 * - Breadcrumb support
 */

interface AssetManagementHeaderProps {
  title: string;
  subtitle?: string;
  showActions?: boolean;
  primaryAction?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  secondaryActions?: Array<{
    label: string;
    onClick?: () => void;
    href?: string;
    icon?: React.ReactNode;
  }>;
  children?: React.ReactNode;
}

export function AssetManagementHeader({
  title,
  subtitle,
  showActions = true,
  primaryAction,
  secondaryActions,
  children,
}: AssetManagementHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-h1 text-text-primary flex items-center gap-2">
          <GradientText variant="action" size="lg">
            {title}
          </GradientText>
        </h1>
        {subtitle && (
          <p className="text-sm text-text-muted mt-1">{subtitle}</p>
        )}
      </div>

      {showActions && (
        <div className="flex items-center gap-2">
          {/* Secondary actions */}
          {secondaryActions?.map((action, index) =>
            action.href ? (
              <Button
                key={index}
                variant="outline"
                size="sm"
                asChild
                className="border-border hover:bg-white/5"
              >
                <Link href={action.href}>
                  {action.icon}
                  <span className="hidden sm:inline ml-2">{action.label}</span>
                </Link>
              </Button>
            ) : (
              <Button
                key={index}
                variant="outline"
                size="sm"
                onClick={action.onClick}
                className="border-border hover:bg-white/5"
              >
                {action.icon}
                <span className="hidden sm:inline ml-2">{action.label}</span>
              </Button>
            )
          )}

          {/* Primary action */}
          {primaryAction && (
            <Button
              size="sm"
              onClick={primaryAction.onClick}
              className="gradient-action text-white hover:opacity-90"
            >
              {primaryAction.icon || <Plus className="w-4 h-4" />}
              <span className="ml-2">{primaryAction.label}</span>
            </Button>
          )}
        </div>
      )}

      {children}
    </div>
  );
}

/**
 * Default header actions for common use cases
 */
export const defaultHeaderActions = {
  novoAtivo: {
    label: "Novo Ativo",
    icon: <Plus className="w-4 h-4" />,
  },
  exportar: {
    label: "Exportar",
    icon: <Download className="w-4 h-4" />,
  },
  buscar: {
    label: "Buscar",
    icon: <Search className="w-4 h-4" />,
  },
};

export default AssetManagementHeader;
