import { AdminSidebar } from '../components/AdminSidebar';
import { Package, ShoppingBag } from 'lucide-react';
import { products, orders } from '../data/mockData';

export function AdminDashboard() {
  const totalProducts = products.length;
  const totalOrders = orders.length;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <AdminSidebar />
      <div className="flex-1">
        <div className="max-w-[1280px] mx-auto px-8 py-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome, Admin</h1>
          <p className="text-gray-600 mb-8">Here's an overview of your store</p>
          
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium mb-1">Total Products</p>
                  <p className="text-4xl font-bold text-gray-900">{totalProducts}</p>
                </div>
                <div className="bg-blue-100 p-4 rounded-lg">
                  <Package className="w-8 h-8 text-blue-600" />
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium mb-1">Total Orders</p>
                  <p className="text-4xl font-bold text-gray-900">{totalOrders}</p>
                </div>
                <div className="bg-green-100 p-4 rounded-lg">
                  <ShoppingBag className="w-8 h-8 text-green-600" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
