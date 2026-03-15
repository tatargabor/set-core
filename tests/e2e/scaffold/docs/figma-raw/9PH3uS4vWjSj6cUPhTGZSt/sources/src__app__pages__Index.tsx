import { Link } from 'react-router';
import { ShoppingBag, ShoppingCart, Package, Lock, LayoutDashboard, Smartphone } from 'lucide-react';

export function Index() {
  const sections = [
    {
      title: 'Storefront Pages',
      icon: ShoppingBag,
      links: [
        { to: '/products', label: 'Product Grid (Desktop)', description: '3x2 grid, 1280px wide' },
        { to: '/mobile', label: 'Product Grid (Mobile)', description: 'Single column, 375px wide' },
        { to: '/product/1', label: 'Product Detail', description: 'Large image with details, 1280px wide' },
      ]
    },
    {
      title: 'Cart & Orders',
      icon: ShoppingCart,
      links: [
        { to: '/cart', label: 'Shopping Cart', description: 'Cart with 3 items' },
        { to: '/orders', label: 'Orders List', description: 'Table with order history' },
        { to: '/orders/1', label: 'Order Detail', description: 'Detailed view of order #1' },
      ]
    },
    {
      title: 'Admin Pages',
      icon: Lock,
      links: [
        { to: '/admin', label: 'Admin Login', description: 'Centered login card' },
        { to: '/admin/dashboard', label: 'Admin Dashboard', description: 'Dashboard with stats' },
        { to: '/admin/products', label: 'Admin Products', description: 'Product management table' },
      ]
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-[1280px] mx-auto px-6 py-12">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">MiniShop</h1>
          <p className="text-xl text-gray-600">Complete E-Commerce Web Application</p>
          <p className="text-gray-500 mt-2">Navigate to any page below to explore the app</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <div key={section.title} className="bg-white rounded-lg shadow-lg p-6 border border-gray-200">
                <div className="flex items-center gap-3 mb-6">
                  <div className="bg-blue-100 p-2 rounded-lg">
                    <Icon className="w-6 h-6 text-blue-600" />
                  </div>
                  <h2 className="text-xl font-bold text-gray-900">{section.title}</h2>
                </div>
                <div className="space-y-4">
                  {section.links.map((link) => (
                    <Link
                      key={link.to}
                      to={link.to}
                      className="block p-4 bg-gray-50 rounded-lg hover:bg-blue-50 hover:border-blue-200 border border-gray-200 transition-all group"
                    >
                      <p className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                        {link.label}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">{link.description}</p>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-12 bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="font-bold text-gray-900 mb-3">Features:</h3>
          <ul className="grid grid-cols-2 gap-3 text-gray-600">
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Responsive design (1280px & 375px)
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Product catalog with stock badges
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Shopping cart with quantity controls
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Order management system
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Admin panel with sidebar navigation
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> shadcn/ui aesthetic with Inter font
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}