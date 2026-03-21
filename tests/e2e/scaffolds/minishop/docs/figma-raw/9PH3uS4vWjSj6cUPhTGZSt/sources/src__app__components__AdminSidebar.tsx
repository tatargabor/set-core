import { Link, useLocation } from 'react-router';
import { LayoutDashboard, Package, LogOut } from 'lucide-react';

export function AdminSidebar() {
  const location = useLocation();
  
  const links = [
    { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/admin/products', label: 'Products', icon: Package },
  ];

  return (
    <div className="w-64 bg-gray-900 text-white min-h-screen">
      <div className="p-6">
        <h2 className="text-xl font-bold">Admin Panel</h2>
      </div>
      <nav className="px-3">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <Icon className="w-5 h-5" />
              {link.label}
            </Link>
          );
        })}
        <Link
          to="/admin"
          className="flex items-center gap-3 px-4 py-3 rounded-lg mb-1 text-gray-300 hover:bg-gray-800 transition-colors mt-4"
        >
          <LogOut className="w-5 h-5" />
          Logout
        </Link>
      </nav>
    </div>
  );
}
