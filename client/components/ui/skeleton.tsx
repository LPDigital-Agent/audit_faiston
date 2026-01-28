import { cn } from "@/lib/utils"

/**
 * Skeleton - Loading placeholder component
 *
 * Standard shadcn/ui skeleton with dark theme styling.
 * Uses subtle pulse animation for loading states.
 */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-white/10",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
