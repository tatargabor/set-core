import { useParams, Link } from 'react-router';
import { Navbar } from '../components/Navbar';
import { orders } from '../data/mockData';
import { ArrowLeft } from 'lucide-react';

export function OrderDetail() {
  const { id } = useParams();
  const order = orders.find(o => o.id === Number(id));

  if (!order) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          <p>Order not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <Link to="/orders" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Orders
        </Link>
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Order #{order.id}</h1>
            <span className={`px-4 py-2 rounded-full text-sm font-medium ${
              order.status === 'Completed'
                ? 'bg-green-100 text-green-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {order.status}
            </span>
          </div>
          <div className="mb-6">
            <p className="text-gray-600">Order Date: {new Date(order.date).toLocaleDateString()}</p>
          </div>
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Product</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Qty</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Price</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Subtotal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {order.items.map((item, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 text-gray-900">{item.productName}</td>
                    <td className="px-6 py-4 text-gray-600">{item.quantity}</td>
                    <td className="px-6 py-4 text-gray-600">€{item.price.toFixed(2)}</td>
                    <td className="px-6 py-4 font-medium text-gray-900">€{(item.price * item.quantity).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end mt-6 pt-6 border-t border-gray-200">
            <div className="text-right">
              <p className="text-gray-600 mb-2">Order Total</p>
              <p className="text-3xl font-bold text-gray-900">€{order.total.toFixed(2)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}