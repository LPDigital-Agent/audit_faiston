"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

/**
 * BentoGrid - Modular dashboard grid layout
 *
 * Implements the Bento Grid design pattern for dashboard widgets.
 * Responsive: 4 cols (desktop) → 2 cols (tablet) → 1 col (mobile)
 */

interface BentoGridProps {
  children: React.ReactNode;
  className?: string;
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid gap-4",
        "grid-cols-1 md:grid-cols-2 lg:grid-cols-4",
        "auto-rows-[minmax(140px,auto)]",
        className
      )}
    >
      {children}
    </div>
  );
}

/**
 * BentoItem - Individual grid item wrapper
 *
 * Supports different sizes through col/row spans
 */

interface BentoItemProps {
  children: React.ReactNode;
  className?: string;
  /** Column span (1-4) */
  colSpan?: 1 | 2 | 3 | 4;
  /** Row span (1-3) */
  rowSpan?: 1 | 2 | 3;
  /** Delay for staggered animation */
  delay?: number;
}

const colSpanClasses = {
  1: "col-span-1",
  2: "col-span-1 md:col-span-2",
  3: "col-span-1 md:col-span-2 lg:col-span-3",
  4: "col-span-1 md:col-span-2 lg:col-span-4",
};

const rowSpanClasses = {
  1: "row-span-1",
  2: "row-span-1 md:row-span-2",
  3: "row-span-1 md:row-span-2 lg:row-span-3",
};

export function BentoItem({
  children,
  className,
  colSpan = 1,
  rowSpan = 1,
  delay = 0,
}: BentoItemProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        delay: delay * 0.1,
        ease: [0.16, 1, 0.3, 1],
      }}
      className={cn(
        colSpanClasses[colSpan],
        rowSpanClasses[rowSpan],
        className
      )}
    >
      {children}
    </motion.div>
  );
}

export default BentoGrid;
