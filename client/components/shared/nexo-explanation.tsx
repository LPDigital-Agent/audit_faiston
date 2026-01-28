"use client";

import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import * as React from "react";
import Image from "next/image";

/**
 * NexoExplanation - NEXO AI contextual explanation component
 *
 * NEXO speaks directly to the user in first-person voice.
 * Uses NEXO avatar to humanize the interaction.
 *
 * Features:
 * - NEXO avatar instead of text label (humanized)
 * - First-person voice ("Eu encontrei..." not "NEXO encontrou...")
 * - Summary always visible (1-2 sentences)
 * - Expandable details section ("Saiba mais")
 * - Optional action guidance
 * - Variant styling (info, tip, warning, success)
 * - Glassmorphism with Faiston brand gradients
 */

export interface NexoExplanationProps {
  /** Optional ref for the container */
  ref?: React.Ref<HTMLDivElement>;
  /** Brief summary always visible (1-2 sentences) - MUST be in first person */
  summary: string;
  /** Expandable detailed explanation - MUST be in first person */
  details?: string;
  /** Action guidance or recommendation */
  action?: string;
  /** Visual variant */
  variant?: "info" | "tip" | "warning" | "success";
  /** Compact mode for inline use */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Default expanded state */
  defaultExpanded?: boolean;
}

const variantConfig = {
  info: {
    gradient: "from-faiston-blue-dark/20 to-faiston-blue-light/20",
    border: "border-faiston-blue-light/30",
    ring: "ring-faiston-blue-light/50",
  },
  tip: {
    gradient: "from-faiston-magenta-dark/20 to-faiston-magenta-light/20",
    border: "border-faiston-magenta-light/30",
    ring: "ring-faiston-magenta-light/50",
  },
  warning: {
    gradient: "from-amber-500/20 to-orange-500/20",
    border: "border-amber-400/30",
    ring: "ring-amber-400/50",
  },
  success: {
    gradient: "from-emerald-500/20 to-teal-500/20",
    border: "border-emerald-400/30",
    ring: "ring-emerald-400/50",
  },
};

export function NexoExplanation({
  ref,
  summary,
  details,
  action,
  variant = "info",
  compact = false,
  className,
  defaultExpanded = false,
}: NexoExplanationProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const config = variantConfig[variant];

  const hasExpandableContent = !!(details || action);

  // Avatar size based on compact mode
  const avatarSize = compact ? 20 : 24;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        // Base glassmorphism
        "relative overflow-hidden rounded-lg",
        "bg-gradient-to-r",
        config.gradient,
        "backdrop-blur-sm",
        "border",
        config.border,
        // Padding based on compact mode
        compact ? "p-2.5" : "p-3",
        // Transition
        "transition-all duration-200",
        className
      )}
    >
      {/* Header with NEXO avatar and summary */}
      <div
        className={cn(
          "flex items-start gap-2.5",
          hasExpandableContent && "cursor-pointer select-none"
        )}
        onClick={() => hasExpandableContent && setIsExpanded(!isExpanded)}
        onKeyDown={(e) => {
          if (hasExpandableContent && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
        tabIndex={hasExpandableContent ? 0 : undefined}
        role={hasExpandableContent ? "button" : undefined}
        aria-expanded={hasExpandableContent ? isExpanded : undefined}
      >
        {/* NEXO Avatar */}
        <div
          className={cn(
            "flex-shrink-0 rounded-full overflow-hidden ring-2",
            config.ring
          )}
          style={{ width: avatarSize, height: avatarSize }}
        >
          <Image
            src="/Avatars/nexo-avatar.png"
            alt="NEXO"
            width={avatarSize}
            height={avatarSize}
            className="object-cover"
          />
        </div>

        {/* Content - NEXO speaks in first person */}
        <div className="flex-1 min-w-0">
          <div className={cn("text-text-primary/90", compact ? "text-xs" : "text-sm")}>
            {summary}
          </div>
        </div>

        {/* Expand indicator */}
        {hasExpandableContent && (
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="flex-shrink-0 mt-0.5"
          >
            <ChevronDown
              className={cn(
                "text-text-muted",
                compact ? "w-3.5 h-3.5" : "w-4 h-4"
              )}
            />
          </motion.div>
        )}
      </div>

      {/* Expandable content */}
      <AnimatePresence initial={false}>
        {isExpanded && hasExpandableContent && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className={cn("pt-2 mt-2 border-t border-white/5", compact ? "pl-7" : "pl-8")}>
              {/* Details */}
              {details && (
                <p
                  className={cn(
                    "text-text-secondary whitespace-pre-line",
                    compact ? "text-xs" : "text-sm"
                  )}
                >
                  {details}
                </p>
              )}

              {/* Action */}
              {action && (
                <div
                  className={cn(
                    "mt-2 flex items-center gap-1.5",
                    "text-faiston-magenta-light font-medium",
                    compact ? "text-xs" : "text-sm"
                  )}
                >
                  <span aria-hidden>→</span>
                  <span>{action}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default NexoExplanation;
