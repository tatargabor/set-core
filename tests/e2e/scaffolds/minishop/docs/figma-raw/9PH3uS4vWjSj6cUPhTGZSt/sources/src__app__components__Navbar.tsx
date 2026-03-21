import { Link } from 'react-router';
import { ShoppingCart } from 'lucide-react';

export function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-[1280px] mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-2xl font-bold text-gray-900">
            MiniShop
          </Link>
          <div className="flex items-center gap-8">
            <Link to="/products" className="text-gray-700 hover:text-gray-900 transition-colors">
              Products
            </Link>
            <Link to="/cart" className="text-gray-700 hover:text-gray-900 transition-colors flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" />
              Cart
            </Link>
            <Link to="/orders" className="text-gray-700 hover:text-gray-900 transition-colors">
              Orders
            </Link>
            <Link to="/admin" className="text-gray-700 hover:text-gray-900 transition-colors">
              Admin
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

export function MobileNavbar() {
  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-gray-900">
            MiniShop
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/cart" className="text-gray-700">
              <ShoppingCart className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}