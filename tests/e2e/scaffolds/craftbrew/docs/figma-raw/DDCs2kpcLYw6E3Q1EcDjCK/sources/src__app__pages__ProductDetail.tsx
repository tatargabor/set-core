import { useState } from 'react';
import { Link } from 'react-router';
import { Heart, Minus, Plus, ChevronRight } from 'lucide-react';
import { Button } from '../components/Button';
import { StarRating } from '../components/StarRating';
import { Badge } from '../components/Badge';
import { ProductCard } from '../components/ProductCard';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { formatPrice } from '../../lib/utils';
import { toast } from 'sonner';

export default function ProductDetail() {
  const [selectedForm, setSelectedForm] = useState('beans');
  const [selectedSize, setSelectedSize] = useState('500g');
  const [quantity, setQuantity] = useState(1);
  const [isFavorite, setIsFavorite] = useState(false);

  const product = {
    id: 'ethiopia-yirgacheffe',
    name: 'Ethiopia Yirgacheffe',
    image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=800',
    rating: 5,
    reviewCount: 12,
    origin: 'Etiópia',
    roast: 'Világos',
    processing: 'Mosott',
    flavorNotes: ['Virágos', 'Citrusos', 'Jázmin', 'Bergamott'],
    description:
      'Az Ethiopia Yirgacheffe különleges minőségű specialty kávé, amely a legendás etióp Yirgacheffe régióból származik. Mosott feldolgozású, világos pörkölésű kávénk virágos, citrusos aromákkal és egyedi jázmin-bergamott ízvilággal rendelkezik. Tökéletes választás filter kávéhoz és pour over módszerekhez.',
    stock: 45,
    prices: {
      beans: {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'ground-filter': {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'ground-espresso': {
        '250g': 2490,
        '500g': 4680,
        '1kg': 6580,
      },
      'drip-bag': {
        '250g': 2990,
        '500g': 5480,
        '1kg': 7580,
      },
    },
  };

  const recommendedProducts = [
    {
      id: 'v60-dripper',
      name: 'Hario V60 Dripper',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 3990,
      rating: 5,
      reviewCount: 24,
    },
    {
      id: 'v60-filters',
      name: 'V60 Papír Filterek',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 1290,
      rating: 5,
      reviewCount: 18,
    },
    {
      id: 'timemore-scale',
      name: 'Timemore Mérleg',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 12990,
      rating: 5,
      reviewCount: 32,
    },
  ];

  const reviews = [
    {
      id: 1,
      stars: 5,
      title: 'Csodálatos kávé!',
      text: 'Az Ethiopia Yirgacheffe a kedvencem lett! Olyan finom virágos íze van, amit még soha nem tapasztaltam. Minden reggel ezt iszom.',
      author: 'Nagy Petra',
      date: '2026-03-10',
      reply: 'Köszönjük szépen a visszajelzést, Petra! Örülünk, hogy tetszik! 🙂',
    },
    {
      id: 2,
      stars: 5,
      title: 'Friss és finom',
      text: 'Nagyon frissen érkezett, az illat csodálatos volt már a kinyitáskor. V60-ban készítem, tökéletes!',
      author: 'Kovács András',
      date: '2026-03-08',
    },
  ];

  const currentPrice = product.prices[selectedForm as keyof typeof product.prices][selectedSize as keyof typeof product.prices.beans];

  const handleAddToCart = () => {
    toast.success('Termék hozzáadva a kosárhoz');
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-[--color-muted] mb-8">
        <Link to="/" className="hover:text-[--color-secondary]">
          Főoldal
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/kavek" className="hover:text-[--color-secondary]">
          Kávék
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-[--color-text]">{product.name}</span>
      </nav>

      {/* Product Details */}
      <div className="grid md:grid-cols-2 gap-12 mb-16">
        {/* Image */}
        <div className="aspect-square bg-white rounded-lg overflow-hidden">
          <ImageWithFallback src={product.image} alt={product.name} className="w-full h-full object-cover" />
        </div>

        {/* Info */}
        <div>
          <h1 className="mb-4">{product.name}</h1>
          <div className="mb-4">
            <StarRating rating={product.rating} count={product.reviewCount} size="lg" />
          </div>

          <p className="text-3xl font-bold text-[--color-primary] mb-6">{formatPrice(currentPrice)}</p>

          <div className="flex gap-4 mb-4 text-sm">
            <span>
              <strong>Eredet:</strong> {product.origin}
            </span>
            <span>
              <strong>Pörkölés:</strong> {product.roast}
            </span>
            <span>
              <strong>Feldolgozás:</strong> {product.processing}
            </span>
          </div>

          {/* Flavor Notes */}
          <div className="flex flex-wrap gap-2 mb-6">
            {product.flavorNotes.map((note) => (
              <Badge key={note} variant="discount">
                {note}
              </Badge>
            ))}
          </div>

          {/* Variant Selector */}
          <div className="mb-6">
            <label className="block mb-2 font-medium">Forma</label>
            <select
              value={selectedForm}
              onChange={(e) => setSelectedForm(e.target.value)}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3 bg-white"
            >
              <option value="beans">Szemes</option>
              <option value="ground-filter">Őrölt (filter)</option>
              <option value="ground-espresso">Őrölt (eszpresszó)</option>
              <option value="drip-bag">Drip bag</option>
            </select>
          </div>

          {/* Size Selector */}
          <div className="mb-6">
            <label className="block mb-3 font-medium">Méret</label>
            <div className="space-y-3">
              {Object.entries(product.prices.beans).map(([size, price]) => (
                <label key={size} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="size"
                    value={size}
                    checked={selectedSize === size}
                    onChange={(e) => setSelectedSize(e.target.value)}
                    className="w-4 h-4 text-[--color-primary]"
                  />
                  <span>
                    {size} ({formatPrice(product.prices[selectedForm as keyof typeof product.prices][size as keyof typeof product.prices.beans])})
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Stock */}
          <p className="text-[--color-success] mb-6">Készleten: {product.stock} db</p>

          {/* Quantity */}
          <div className="mb-6">
            <label className="block mb-2 font-medium">Mennyiség</label>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
                className="w-11 h-11 border border-[--color-border] rounded-lg flex items-center justify-center hover:bg-[--color-background]"
              >
                <Minus className="w-4 h-4" />
              </button>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-20 h-11 border border-[--color-border] rounded-lg text-center"
              />
              <button
                onClick={() => setQuantity(quantity + 1)}
                className="w-11 h-11 border border-[--color-border] rounded-lg flex items-center justify-center hover:bg-[--color-background]"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-4 mb-6">
            <Button variant="primary" fullWidth onClick={handleAddToCart}>
              Kosárba
            </Button>
            <button
              onClick={() => setIsFavorite(!isFavorite)}
              className="min-w-[44px] h-[44px] border-2 border-[--color-border] rounded-lg flex items-center justify-center hover:border-[--color-secondary]"
            >
              <Heart className={`w-5 h-5 ${isFavorite ? 'fill-[--color-error] text-[--color-error]' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Description */}
      <div className="mb-16">
        <h2 className="mb-4">Leírás</h2>
        <p className="text-[--color-muted] leading-relaxed">{product.description}</p>
      </div>

      {/* Recommended Products */}
      <div className="mb-16">
        <h2 className="mb-8">Ajánljuk mellé</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {recommendedProducts.map((prod) => (
            <ProductCard key={prod.id} {...prod} />
          ))}
        </div>
      </div>

      {/* Reviews */}
      <div>
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="mb-2">Értékelések</h2>
            <StarRating rating={product.rating} count={product.reviewCount} size="lg" />
          </div>
          <Button variant="outlined">Értékelés írása</Button>
        </div>

        <div className="space-y-6">
          {reviews.map((review) => (
            <div key={review.id} className="bg-white p-6 rounded-lg">
              <div className="mb-3">
                <StarRating rating={review.stars} />
              </div>
              <h4 className="font-semibold mb-2">{review.title}</h4>
              <p className="text-[--color-muted] mb-4">{review.text}</p>
              <div className="flex items-center gap-4 text-sm text-[--color-muted]">
                <span className="font-medium text-[--color-text]">{review.author}</span>
                <span>{review.date}</span>
              </div>

              {review.reply && (
                <div className="mt-4 ml-8 pl-4 border-l-2 border-[--color-secondary]">
                  <p className="text-sm font-medium text-[--color-primary] mb-1">CraftBrew válaszolt:</p>
                  <p className="text-sm text-[--color-muted]">{review.reply}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
