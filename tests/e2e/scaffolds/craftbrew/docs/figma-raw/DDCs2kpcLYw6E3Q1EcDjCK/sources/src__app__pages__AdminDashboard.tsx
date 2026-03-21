import { Routes, Route, Link, useLocation } from 'react-router';
import { LayoutDashboard, Package, ShoppingCart, Truck, Calendar, Tag, Gift, Star, Megaphone, FileText } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatPrice } from '../../lib/utils';

function Overview() {
  const chartData = [
    { date: '03-06', revenue: 156000 },
    { date: '03-07', revenue: 189000 },
    { date: '03-08', revenue: 145000 },
    { date: '03-09', revenue: 223000 },
    { date: '03-10', revenue: 198000 },
    { date: '03-11', revenue: 267000 },
    { date: '03-12', revenue: 234500 },
  ];

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Mai bevétel</span>
            <span className="text-xs text-[--color-success]">+12%</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">234 500 Ft</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Mai rendelések</span>
            <span className="text-xs text-[--color-success]">+3</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">8</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Aktív előfizetők</span>
            <span className="text-xs text-[--color-success]">+2</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">23</p>
        </div>
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[--color-muted]">Új regisztrációk (7 nap)</span>
            <span className="text-xs text-[--color-error]">-5%</span>
          </div>
          <p className="text-2xl font-bold text-[--color-primary]">15</p>
        </div>
      </div>

      {/* Revenue Chart */}
      <div className="bg-white rounded-lg p-6 shadow-sm">
        <h3 className="text-lg font-semibold mb-6">Bevétel (7 nap)</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
            <XAxis dataKey="date" stroke="#78716C" />
            <YAxis stroke="#78716C" />
            <Tooltip formatter={(value) => `${formatPrice(value as number)}`} />
            <Bar dataKey="revenue" fill="#D97706" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Top Products & Low Stock */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">Top termékek ma</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center pb-3 border-b border-[--color-border]">
              <span>#1 Ethiopia Yirgacheffe</span>
              <span className="font-semibold">12 db</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-[--color-border]">
              <span>#2 Starter Bundle</span>
              <span className="font-semibold">5 db</span>
            </div>
            <div className="flex justify-between items-center">
              <span>#3 Colombia Huila</span>
              <span className="font-semibold">4 db</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 shadow-sm">
          <h3 className="text-lg font-semibold mb-4">Alacsony készlet ⚠️</h3>
          <div className="space-y-3">
            <div className="p-3 border-l-4 border-[--color-warning] bg-amber-50 rounded">
              <p className="font-medium">Fellow Stagg EKG Kettle</p>
              <p className="text-sm text-[--color-muted]">8 db</p>
            </div>
            <div className="p-3 border-l-4 border-[--color-warning] bg-amber-50 rounded">
              <p className="font-medium">Rwanda Nyungwe 1kg</p>
              <p className="text-sm text-[--color-muted]">5 db</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Products() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Termékek kezelése</h2>
      <p className="text-[--color-muted]">Termék kezelési funkciók itt jelennek meg...</p>
    </div>
  );
}

export default function AdminDashboard() {
  const location = useLocation();
  const currentPath = location.pathname.split('/').pop() || 'overview';

  const menuItems = [
    { path: '', label: 'Áttekintés', icon: LayoutDashboard },
    { path: 'termekek', label: 'Termékek', icon: Package },
    { path: 'rendelesek', label: 'Rendelések', icon: ShoppingCart },
    { path: 'szallitas', label: 'Szállítás', icon: Truck },
    { path: 'elofizetesek', label: 'Előfizetések', icon: Calendar },
    { path: 'kuponok', label: 'Kuponok', icon: Tag },
    { path: 'ajandekkartyak', label: 'Ajándékkártyák', icon: Gift },
    { path: 'ertekelesek', label: 'Értékelések', icon: Star },
    { path: 'promo-napok', label: 'Promó napok', icon: Megaphone },
    { path: 'tartalom', label: 'Tartalom', icon: FileText },
  ];

  return (
    <div className="min-h-screen bg-[--color-background]">
      <div className="flex">
        {/* Sidebar */}
        <aside className="w-64 bg-white h-screen sticky top-0 border-r border-[--color-border]">
          <div className="p-6 border-b border-[--color-border]">
            <h2 className="text-xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew Admin
            </h2>
          </div>
          <nav className="p-4 space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.path || (currentPath === 'admin' && item.path === '');
              return (
                <Link
                  key={item.path}
                  to={`/admin/${item.path}`}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-[--color-background] text-[--color-primary]'
                      : 'text-[--color-muted] hover:bg-[--color-background]'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-8">
          <Routes>
            <Route index element={<Overview />} />
            <Route path="termekek" element={<Products />} />
            <Route path="*" element={<div className="bg-white rounded-lg p-6"><p className="text-[--color-muted]">Ez a funkció hamarosan elérhető lesz...</p></div>} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
