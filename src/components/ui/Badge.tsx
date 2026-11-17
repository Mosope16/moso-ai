import React from 'react';
import { cn } from '../../utils/cn';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'accent' | 'outline' | 'warning' | 'danger' | 'success' | 'muted';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  className,
  variant = 'default',
  size = 'md',
  children,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center font-medium rounded-full transition-colors select-none';

  const variants = {
    default: 'bg-moso-800 text-moso-200 border border-moso-700/60',
    accent: 'bg-moso-accent/15 text-moso-accent border border-moso-accent/30',
    outline: 'bg-transparent text-moso-300 border border-moso-700',
    warning: 'bg-amber-500/15 text-amber-300 border border-amber-500/30',
    danger: 'bg-rose-500/15 text-rose-300 border border-rose-500/30',
    success: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
    muted: 'bg-moso-850 text-moso-400 border border-moso-800',
  };

  const sizes = {
    sm: 'text-[10px] px-1.5 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-0.75 gap-1.5',
  };

  return (
    <span className={cn(baseStyles, variants[variant], sizes[size], className)} {...props}>
      {children}
    </span>
  );
};
