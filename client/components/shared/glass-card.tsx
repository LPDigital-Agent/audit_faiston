"use client";

import { cn } from "@/lib/utils";
import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";

/**
 * GlassCard - Glassmorphism card component following Faiston design system
 *
 * Features:
 * - Frosted glass effect with backdrop blur
 * - Ghost border with hover glow effect
 * - Optional gradient border animation
 * - Framer Motion animations
 */

export interface GlassCardProps extends HTMLMotionProps<"div"> {
  /** Elevated variant with stronger blur and shadow */
  elevated?: boolean;
  /** Animated gradient border */
  gradientBorder?: boolean;
  /** Hover glow effect */
  hoverGlow?: boolean;
  /** Custom padding */
  padding?: "none" | "sm" | "md" | "lg";
}

const paddingClasses = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  (
    {
      className,
      elevated = false,
      gradientBorder = false,
      hoverGlow = true,
      padding = "md",
      children,
      ...props
    },
    ref
  ) => {
    const baseClasses = elevated ? "glass-elevated" : "glass-card";

    return (
      <motion.div
        ref={ref}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
        className={cn(
          baseClasses,
          paddingClasses[padding],
          hoverGlow && "ghost-border",
          gradientBorder && "gradient-border",
          "transition-all duration-200",
          className
        )}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);

GlassCard.displayName = "GlassCard";

/**
 * GlassCardHeader - Header section for GlassCard
 */
export function GlassCardHeader({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex items-center justify-between mb-4", className)}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * GlassCardTitle - Title for GlassCard header
 */
export function GlassCardTitle({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn("text-h2 text-text-primary", className)} {...props}>
      {children}
    </h3>
  );
}

/**
 * GlassCardContent - Content section for GlassCard
 */
export function GlassCardContent({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("text-body text-text-secondary", className)} {...props}>
      {children}
    </div>
  );
}

export default GlassCard;
