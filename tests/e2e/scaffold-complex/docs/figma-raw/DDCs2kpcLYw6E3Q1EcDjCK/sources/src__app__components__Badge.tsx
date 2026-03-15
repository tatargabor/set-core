import { cn } from '../../lib/utils';

interface BadgeProps {
  variant: 'new' | 'outOfStock' | 'lowStock' | 'discount' | 'category' | 'status';
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'category', className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium',
        {
          'bg-[--color-success] text-white': variant === 'new',
          'bg-[--color-error] text-white': variant === 'outOfStock',
          'bg-[--color-warning] text-white': variant === 'lowStock' || variant === 'discount',
          'bg-[--color-primary] text-white': variant === 'category',
          'bg-[--color-muted] text-white': variant === 'status',
        },
        className
      )}
    >
      {children}
    </span>
  );
}