import React from 'react';
import { cn } from '../../utils/cn';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline' | 'accent';
  size?: 'sm' | 'md' | 'lg' | 'icon' | 'icon-sm';
  isLoading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'secondary', size = 'md', isLoading, disabled, children, ...props }, ref) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all duration-150 rounded-lg select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-moso-accent/50 active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none disabled:active:scale-100 cursor-pointer';

    const variants = {
      primary:
        'bg-moso-accent text-moso-950 hover:bg-moso-accent-hover font-semibold shadow-sm shadow-moso-accent/20',
      accent:
        'bg-moso-accent/15 text-moso-accent hover:bg-moso-accent/25 border border-moso-accent/30',
      secondary:
        'bg-moso-800 text-moso-100 hover:bg-moso-750 hover:text-white border border-moso-700/60 shadow-xs',
      ghost:
        'bg-transparent text-moso-300 hover:text-white hover:bg-moso-800/60',
      danger:
        'bg-rose-500/15 text-rose-300 hover:bg-rose-500/25 border border-rose-500/30 hover:text-rose-200',
      outline:
        'bg-transparent text-moso-200 border border-moso-700 hover:border-moso-600 hover:bg-moso-850',
    };

    const sizes = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5',
      md: 'text-sm px-3.5 py-2 gap-2',
      lg: 'text-base px-4 py-2.5 gap-2.5',
      icon: 'h-9 w-9 p-0',
      'icon-sm': 'h-7 w-7 p-0',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading ? (
          <div className="h-4 w-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        ) : (
          children
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
