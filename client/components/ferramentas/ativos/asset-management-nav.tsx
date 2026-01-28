"use client";

import { cn } from "@/lib/utils";
import { ASSET_NAV_MODULES } from "@/lib/ativos/constants";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

/**
 * AssetManagementNav - Horizontal tab navigation for Asset Management modules
 *
 * Features:
 * - Horizontal scrollable tabs for 7 modules
 * - Active state with gradient underline indicator
 * - Badge support for notifications
 * - Responsive (icons only on mobile)
 * - Smooth animations with Framer Motion
 */

export function AssetManagementNav() {
  const pathname = usePathname();

  // Determine active module based on pathname
  const getActiveModule = () => {
    // Check for exact match or subpath match
    for (const navModule of ASSET_NAV_MODULES) {
      if (pathname === navModule.href || pathname.startsWith(navModule.href + "/")) {
        return navModule.id;
      }
    }
    // Default to dashboard if on base path
    if (pathname === "/ferramentas/ativos") {
      return "dashboard";
    }
    return null;
  };

  const activeModule = getActiveModule();

  return (
    <nav className="border-b border-border">
      <div className="flex items-center gap-1 overflow-x-auto pb-px scrollbar-hide">
        {ASSET_NAV_MODULES.map((module) => {
          const Icon = module.icon;
          const isActive = activeModule === module.id;

          return (
            <Link
              key={module.id}
              href={module.href}
              className={cn(
                "relative flex items-center gap-2 px-4 py-3",
                "text-sm font-medium whitespace-nowrap",
                "transition-all duration-150",
                "hover:text-text-primary",
                isActive
                  ? "text-text-primary"
                  : "text-text-secondary hover:bg-white/5"
              )}
            >
              <Icon className={cn(
                "w-4 h-4 shrink-0",
                isActive ? "text-magenta-light" : "text-text-muted"
              )} />

              {/* Full label on desktop, short on mobile */}
              <span className="hidden sm:inline">{module.label}</span>
              <span className="sm:hidden">{module.labelShort || module.label}</span>

              {/* Badge for notifications */}
              {module.badge && module.badge > 0 && (
                <Badge
                  variant="default"
                  className="ml-1 px-1.5 py-0 text-xs bg-magenta-mid text-white"
                >
                  {module.badge}
                </Badge>
              )}

              {/* Active indicator - gradient underline */}
              {isActive && (
                <motion.div
                  layoutId="activeAssetTab"
                  className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full"
                  style={{
                    background: "linear-gradient(90deg, #960A9C, #FD11A4, #FD5665)",
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 500,
                    damping: 30,
                  }}
                />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export default AssetManagementNav;
