import { useState } from 'react';
import { Link } from 'react-router';
import { Navbar } from '../components/Navbar';
import { initialCart } from '../data/mockData';
import { Minus, Plus, Trash2, ShoppingCart } from 'lucide-react';

export function Cart() {
  const [cartItems, setCartItems] = useState(initialCart);

  const updateQuantity = (productId: number, delta: number) => {
    setCartItems(items => 
      items.map(item => 
        item.product.id === productId 
          ? { ...item, quantity: Math.max(1, item.quantity + delta) }
          : item
      )
    );
  };

  const removeItem = (productId: number) => {
    setCartItems(items => items.filter(item => item.product.id !== productId));
  };

  const total = cartItems.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);

  if (cartItems.length === 0) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <div className="max-w-[1280px] mx-auto px-6 py-16">
          <div className="flex flex-col items-center justify-center py-16">
            <ShoppingCart className="w-24 h-24 text-gray-300 mb-6" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Your cart is empty</h2>
            <p className="text-gray-600 mb-6">Add some products to get started</p>
            <Link 
              to="/products"
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Shopping Cart ({cartItems.length} items)</h1>
        <div className="bg-white rounded-lg shadow-md p-6 mt-6">
          <div className="divide-y divide-gray-200">
            {cartItems.map(item => (
              <div key={item.product.id} className="py-6 flex items-center gap-6">
                <div className="w-24 h-24 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                  <img 
                    src={item.product.image} 
                    alt={item.product.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg text-gray-900">{item.product.name}</h3>
                  <p className="text-sm text-gray-600">{item.product.shortDescription}</p>
                  <p className="text-gray-900 font-medium mt-1">€{item.product.price.toFixed(2)}</p>
                </div>
                <div className="flex items-center gap-3 bg-gray-100 rounded-lg px-3 py-2">
                  <button 
                    onClick={() => updateQuantity(item.product.id, -1)}
                    className="text-gray-600 hover:text-gray-900"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="font-medium w-8 text-center">{item.quantity}</span>
                  <button 
                    onClick={() => updateQuantity(item.product.id, 1)}
                    className="text-gray-600 hover:text-gray-900"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
                <div className="w-24 text-right font-bold text-gray-900">
                  €{(item.product.price * item.quantity).toFixed(2)}
                </div>
                <button 
                  onClick={() => removeItem(item.product.id)}
                  className="text-red-500 hover:text-red-700 transition-colors"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            ))}
          </div>
          <div className="border-t border-gray-200 pt-6 mt-6">
            <div className="flex items-center justify-between mb-6">
              <span className="text-xl font-bold text-gray-900">Total:</span>
              <span className="text-3xl font-bold text-gray-900">€{total.toFixed(2)}</span>
            </div>
            <button className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium text-lg hover:bg-blue-700 transition-colors">
              Place Order
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}