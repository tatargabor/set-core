import { Star } from 'lucide-react';
import { cn } from '../../lib/utils';

interface StarRatingProps {
  rating: number;
  count?: number;
  size?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
  onRate?: (rating: number) => void;
}

export function StarRating({ rating, count, size = 'md', interactive = false, onRate }: StarRatingProps) {
  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const handleClick = (index: number) => {
    if (interactive && onRate) {
      onRate(index + 1);
    }
  };

  return (
    <div className="flex items-center gap-1">
      {[0, 1, 2, 3, 4].map((index) => (
        <Star
          key={index}
          className={cn(
            sizeClasses[size],
            index < rating ? 'fill-[--color-secondary] text-[--color-secondary]' : 'text-[--color-border]',
            interactive && 'cursor-pointer hover:scale-110 transition-transform'
          )}
          onClick={() => handleClick(index)}
        />
      ))}
      {count !== undefined && (
        <span className="ml-1 text-sm text-[--color-muted]">({count})</span>
      )}
    </div>
  );
}
