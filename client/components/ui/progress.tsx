'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Optional ref for the progress container */
  ref?: React.Ref<HTMLDivElement>;
  value?: number;
  max?: number;
}

function Progress({ ref, className, value = 0, max = 100, ...props }: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div
      ref={ref}
      className={cn(
        'relative h-2 w-full overflow-hidden rounded-full bg-white/10',
        className
      )}
      {...props}
    >
      <div
        className="h-full bg-gradient-to-r from-magenta-mid to-blue-mid transition-all duration-300 ease-out"
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}

export { Progress };
