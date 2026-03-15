import { MobileNavbar } from '../components/Navbar';
import { ProductCard } from '../components/ProductCard';
import { products } from '../data/mockData';

export function MobileProductGrid() {
  return (
    <div className="min-h-screen bg-white w-[375px] mx-auto">
      <MobileNavbar />
      <div className="px-4 py-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Our Products</h1>
        <div className="flex flex-col gap-4">
          {products.map(product => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </div>
    </div>
  );
}