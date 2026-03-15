import { ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'outlined';
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', fullWidth, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          'min-h-[44px] px-6 py-3 rounded-[6px] transition-all duration-200 font-medium',
          {
            'bg-[--color-primary] text-white hover:bg-[#5a2808] active:bg-[#4a2006]': variant === 'primary' && !disabled,
            'border-2 border-[--color-primary] text-[--color-primary] hover:bg-[--color-primary] hover:text-white': variant === 'outlined' && !disabled,
            'border-2 border-[--color-secondary] text-[--color-secondary] hover:bg-[--color-secondary] hover:text-white': variant === 'secondary' && !disabled,
            'text-[--color-primary] hover:bg-[--color-background]': variant === 'ghost' && !disabled,
            'opacity-50 cursor-not-allowed': disabled,
            'w-full': fullWidth,
          },
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';