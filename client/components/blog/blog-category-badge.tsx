"use client";

import { cn } from "@/lib/utils";
import { BlogCategory, getCategoryConfig } from "@/lib/blog/types";

/**
 * BlogCategoryBadge - Category badge with semantic colors
 *
 * Displays category labels with colors matching the Faiston design system:
 * - Seguranca: Red
 * - Infraestrutura: Blue
 * - Cloud: Cyan
 * - Inovacao: Magenta
 * - Blog & News: Green
 */

interface BlogCategoryBadgeProps {
  /** Category slug */
  category: BlogCategory;
  /** Optional custom class names */
  className?: string;
  /** Size variant */
  size?: "sm" | "md";
}

export function BlogCategoryBadge({
  category,
  className,
  size = "sm",
}: BlogCategoryBadgeProps) {
  const config = getCategoryConfig(category);

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        config.bgClass,
        config.textClass,
        config.borderClass,
        "border",
        size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
        className
      )}
    >
      {config.label}
    </span>
  );
}

export default BlogCategoryBadge;
