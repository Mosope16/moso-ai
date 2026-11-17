import React from 'react';
import { cn } from '../../utils/cn';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, type = 'text', ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full">
        {icon && (
          <div className="absolute left-3 text-moso-400 pointer-events-none flex items-center">
            {icon}
          </div>
        )}
        <input
          ref={ref}
          type={type}
          className={cn(
            'w-full bg-moso-900 border border-moso-700/70 rounded-lg text-sm text-moso-100 placeholder:text-moso-500 py-2 transition-all duration-150',
            'focus:outline-none focus:border-moso-accent/60 focus:ring-1 focus:ring-moso-accent/40',
            'hover:border-moso-600',
            icon ? 'pl-9 pr-3' : 'px-3',
            className
          )}
          {...props}
        />
      </div>
    );
  }
);

Input.displayName = 'Input';
