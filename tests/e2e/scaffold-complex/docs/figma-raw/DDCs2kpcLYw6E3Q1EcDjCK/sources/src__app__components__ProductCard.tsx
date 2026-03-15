import { Heart } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router';
import { Badge } from './Badge';
import { StarRating } from './StarRating';
import { formatPrice } from '../../lib/utils';
import { ImageWithFallback } from './figma/ImageWithFallback';

interface ProductCardProps {
  id: string;
  name: string;
  image: string;
  price: number;
  rating?: number;
  reviewCount?: number;
  isNew?: boolean;
  isOutOfStock?: boolean;
  origin?: string;
  roast?: string;
}

export function ProductCard({
  id,
  name,
  image,
  price,
  rating = 5,
  reviewCount = 0,
  isNew,
  isOutOfStock,
  origin,
  roast,
}: ProductCardProps) {
  const [isFavorite, setIsFavorite] = useState(false);

  return (
    <div className="bg-white rounded-[8px] p-6 relative group hover:shadow-lg hover:border-[--color-secondary] border-2 border-transparent transition-all duration-200">
      {/* Heart Icon */}
      <button
        onClick={(e) => {
          e.preventDefault();
          setIsFavorite(!isFavorite);
        }}
        className="absolute top-4 right-4 z-10 p-2 rounded-full bg-white/80 hover:bg-white transition-colors"
      >
        <Heart
          className={`w-5 h-5 ${
            isFavorite ? 'fill-[--color-error] text-[--color-error]' : 'text-[--color-muted]'
          }`}
        />
      </button>

      {/* Badges */}
      <div className="absolute top-4 left-4 z-10 flex flex-col gap-2">
        {isNew && <Badge variant="new">Új</Badge>}
        {isOutOfStock && <Badge variant="outOfStock">Elfogyott</Badge>}
      </div>

      <Link to={`/kavek/${id}`} className="block">
        {/* Image */}
        <div className="aspect-[4/3] mb-4 overflow-hidden rounded">
          <ImageWithFallback
            src={image}
            alt={name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
        </div>

        {/* Tags */}
        {(origin || roast) && (
          <div className="flex gap-2 mb-2">
            {origin && <Badge variant="category">{origin}</Badge>}
            {roast && <Badge variant="category">{roast}</Badge>}
          </div>
        )}

        {/* Name */}
        <h3 className="text-xl mb-2">{name}</h3>

        {/* Rating */}
        <div className="mb-3">
          <StarRating rating={rating} count={reviewCount} />
        </div>

        {/* Price */}
        <p className="text-lg font-semibold text-[--color-primary]">
          {formatPrice(price)}-tól
        </p>
      </Link>
    </div>
  );
}