"use client";

import { cn } from "@/lib/utils";

/**
 * GradientText - Text with Faiston brand gradient
 *
 * Applies the official Faiston gradients to text.
 * Two variants: nexo (blue) and action (magenta)
 */

export interface GradientTextProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Gradient variant */
  variant?: "nexo" | "action";
  /** Text size class */
  size?: "sm" | "md" | "lg" | "xl" | "hero";
  /** Make text bold */
  bold?: boolean;
}

const sizeClasses = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg",
  xl: "text-xl",
  hero: "text-hero",
};

export function GradientText({
  variant = "nexo",
  size = "md",
  bold = false,
  className,
  children,
  ...props
}: GradientTextProps) {
  const gradientClass =
    variant === "nexo" ? "gradient-text-nexo" : "gradient-text-action";

  return (
    <span
      className={cn(
        gradientClass,
        sizeClasses[size],
        bold && "font-bold",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export default GradientText;
