"use client";

import { cn } from "@/lib/utils";
import Image from "next/image";

/**
 * FaistonLogo - Official Faiston logo component
 *
 * Uses the official logo assets from the Faiston brand manual.
 * Supports different variants for different backgrounds.
 */

export interface FaistonLogoProps {
  /** Logo variant based on background */
  variant?: "white" | "negative" | "positive" | "color";
  /** Size preset */
  size?: "sm" | "md" | "lg" | "xl";
  /** Custom className */
  className?: string;
  /** Show text or icon only */
  iconOnly?: boolean;
}

const sizeClasses = {
  sm: { width: 80, height: 24 },
  md: { width: 120, height: 36 },
  lg: { width: 160, height: 48 },
  xl: { width: 200, height: 60 },
};

const logoSources = {
  white: "/logos/faiston-white.png",
  negative: "/logos/faiston-negative.png",
  positive: "/logos/faiston-positive.png",
  color: "/logos/faiston-color.png",
};

export function FaistonLogo({
  variant = "white",
  size = "md",
  className,
  iconOnly = false,
}: FaistonLogoProps) {
  const dimensions = sizeClasses[size];

  return (
    <div className={cn("relative flex items-center", className)}>
      <Image
        src={logoSources[variant]}
        alt="Faiston"
        width={iconOnly ? dimensions.height : dimensions.width}
        height={dimensions.height}
        className="object-contain"
        priority
      />
    </div>
  );
}

/**
 * FaistonIcon - Just the F icon from the logo
 * Uses the triangle + F mark only
 */
export function FaistonIcon({
  size = "md",
  className,
}: Pick<FaistonLogoProps, "size" | "className">) {
  const iconSize = sizeClasses[size].height;

  return (
    <div
      className={cn(
        "relative flex items-center justify-center",
        "rounded-lg overflow-hidden",
        className
      )}
      style={{ width: iconSize, height: iconSize }}
    >
      {/* Gradient background matching Faiston brand */}
      <div className="absolute inset-0 gradient-nexo opacity-90" />
      <span className="relative text-white font-bold text-lg">F</span>
    </div>
  );
}

export default FaistonLogo;
