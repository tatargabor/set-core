import { useState } from 'react';
import { ChevronDown, ChevronUp, SlidersHorizontal } from 'lucide-react';
import { ProductCard } from '../components/ProductCard';

export default function ProductCatalog() {
  const [showFilters, setShowFilters] = useState(true);
  const [filters, setFilters] = useState({
    origin: [] as string[],
    roast: [] as string[],
    processing: [] as string[],
    priceMin: 1990,
    priceMax: 9380,
  });

  const origins = ['Etiópia', 'Kolumbia', 'Brazília', 'Guatemala', 'Kenya', 'Indonézia', 'Costa Rica', 'Ruanda'];
  const roastLevels = ['Világos', 'Közepes', 'Sötét'];
  const processingMethods = ['Mosott', 'Természetes', 'Mézes', 'Wet-hulled'];

  const products = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
      isNew: true,
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
      roast: 'Közepes',
    },
    {
      id: 'kenya-aa',
      name: 'Kenya AA',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?w=400',
      price: 3190,
      rating: 5,
      reviewCount: 15,
      origin: 'Kenya',
      roast: 'Világos',
    },
    {
      id: 'brazil-santos',
      name: 'Brazil Santos',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?w=400',
      price: 2290,
      rating: 4,
      reviewCount: 10,
      origin: 'Brazília',
      roast: 'Sötét',
    },
    {
      id: 'guatemala-antigua',
      name: 'Guatemala Antigua',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2990,
      rating: 5,
      reviewCount: 7,
      origin: 'Guatemala',
      roast: 'Közepes',
    },
    {
      id: 'costa-rica-tarrazu',
      name: 'Costa Rica Tarrazú',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 3290,
      rating: 5,
      reviewCount: 9,
      origin: 'Costa Rica',
      roast: 'Világos',
    },
    {
      id: 'indonesia-sumatra',
      name: 'Indonesia Sumatra',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?w=400',
      price: 2590,
      rating: 4,
      reviewCount: 11,
      origin: 'Indonézia',
      roast: 'Sötét',
    },
    {
      id: 'rwanda-nyungwe',
      name: 'Rwanda Nyungwe',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?w=400',
      price: 3390,
      rating: 5,
      reviewCount: 6,
      origin: 'Ruanda',
      roast: 'Világos',
      isNew: true,
    },
  ];

  const FilterSection = ({ title, items, filterKey }: { title: string; items: string[]; filterKey: string }) => {
    const [expanded, setExpanded] = useState(true);

    return (
      <div className="border-b border-[--color-border] pb-4 mb-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-between w-full mb-3 font-medium"
        >
          {title}
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
        {expanded && (
          <div className="space-y-2">
            {items.map((item) => (
              <label key={item} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-[--color-border] text-[--color-primary] focus:ring-[--color-secondary]"
                  onChange={(e) => {
                    const key = filterKey as keyof typeof filters;
                    if (e.target.checked) {
                      setFilters({
                        ...filters,
                        [key]: [...(filters[key] as string[]), item],
                      });
                    } else {
                      setFilters({
                        ...filters,
                        [key]: (filters[key] as string[]).filter((i) => i !== item),
                      });
                    }
                  }}
                />
                <span className="text-sm">{item}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Page Title */}
      <h1 className="mb-8">Kávék</h1>

      <div className="flex flex-col md:flex-row gap-8">
        {/* Mobile Filter Button */}
        <button
          className="md:hidden flex items-center justify-center gap-2 bg-white border border-[--color-border] rounded-lg px-4 py-3"
          onClick={() => setShowFilters(!showFilters)}
        >
          <SlidersHorizontal className="w-5 h-5" />
          Szűrők
        </button>

        {/* Filters Sidebar */}
        <aside
          className={`${
            showFilters ? 'block' : 'hidden'
          } md:block w-full md:w-72 bg-white rounded-lg p-6 h-fit sticky top-24`}
        >
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold">Szűrők</h3>
            <button
              className="text-sm text-[--color-secondary] hover:underline"
              onClick={() =>
                setFilters({
                  origin: [],
                  roast: [],
                  processing: [],
                  priceMin: 1990,
                  priceMax: 9380,
                })
              }
            >
              Szűrők törlése
            </button>
          </div>

          <FilterSection title="Eredet" items={origins} filterKey="origin" />
          <FilterSection title="Pörkölés" items={roastLevels} filterKey="roast" />
          <FilterSection title="Feldolgozás" items={processingMethods} filterKey="processing" />

          {/* Price Range */}
          <div className="border-b border-[--color-border] pb-4 mb-4">
            <h4 className="font-medium mb-3">Ár</h4>
            <div className="space-y-3">
              <input
                type="range"
                min="1990"
                max="9380"
                value={filters.priceMin}
                onChange={(e) => setFilters({ ...filters, priceMin: parseInt(e.target.value) })}
                className="w-full"
              />
              <div className="flex gap-2">
                <input
                  type="number"
                  value={filters.priceMin}
                  onChange={(e) => setFilters({ ...filters, priceMin: parseInt(e.target.value) })}
                  className="w-full border border-[--color-border] rounded px-3 py-2 text-sm"
                  placeholder="Min"
                />
                <input
                  type="number"
                  value={filters.priceMax}
                  onChange={(e) => setFilters({ ...filters, priceMax: parseInt(e.target.value) })}
                  className="w-full border border-[--color-border] rounded px-3 py-2 text-sm"
                  placeholder="Max"
                />
              </div>
            </div>
          </div>
        </aside>

        {/* Product Grid */}
        <div className="flex-1">
          {/* Sorting */}
          <div className="flex justify-end mb-6">
            <select className="border border-[--color-border] rounded-lg px-4 py-2 bg-white">
              <option>Rendezés: Népszerű</option>
              <option>Ár ↑</option>
              <option>Ár ↓</option>
              <option>Legújabb</option>
            </select>
          </div>

          {/* Products */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {products.map((product) => (
              <ProductCard key={product.id} {...product} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
