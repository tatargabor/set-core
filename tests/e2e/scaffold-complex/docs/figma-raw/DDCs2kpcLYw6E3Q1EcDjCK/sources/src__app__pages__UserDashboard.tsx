import { Routes, Route, Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart } from 'lucide-react';
import { Button } from '../components/Button';
import { formatPrice } from '../../lib/utils';

function Profile() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Adataim</h2>
      <div className="space-y-4 max-w-md">
        <div>
          <label className="block mb-2">Név</label>
          <input type="text" defaultValue="Kiss János" className="w-full border border-[--color-border] rounded-lg px-4 py-3" />
        </div>
        <div>
          <label className="block mb-2">Email</label>
          <input type="email" defaultValue="kiss.janos@example.com" className="w-full border border-[--color-border] rounded-lg px-4 py-3" readOnly />
        </div>
        <div>
          <label className="block mb-2">Nyelv</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input type="radio" name="lang" defaultChecked />
              <span>HU</span>
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="lang" />
              <span>EN</span>
            </label>
          </div>
        </div>
        <Button variant="primary">Mentés</Button>
      </div>
    </div>
  );
}

function Addresses() {
  const addresses = [
    { id: 1, label: 'Otthon', name: 'Kiss János', address: '1052 Budapest, Váci u. 10', phone: '+36 20 123 4567', zone: 'Budapest', isDefault: true },
    { id: 2, label: 'Iroda', name: 'Kiss János', address: '1075 Budapest, Kazinczy u. 28', phone: '+36 20 123 4567', zone: 'Budapest', isDefault: false },
  ];

  return (
    <div className="bg-white rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2>Címeim</h2>
        <Button variant="primary">+ Új cím</Button>
      </div>
      <div className="space-y-4">
        {addresses.map((addr) => (
          <div key={addr.id} className="border border-[--color-border] rounded-lg p-4">
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-semibold mb-1">{addr.label} {addr.isDefault && <span className="text-xs text-[--color-secondary]">★ Alapértelmezett</span>}</p>
                <p className="text-sm text-[--color-muted]">{addr.name}</p>
                <p className="text-sm text-[--color-muted]">{addr.address}</p>
                <p className="text-sm text-[--color-muted]">{addr.phone}</p>
                <span className="inline-block mt-2 px-2 py-1 bg-[--color-success] text-white text-xs rounded">{addr.zone}</span>
              </div>
              <div className="flex gap-2">
                <button className="text-sm text-[--color-secondary] hover:underline">Szerkesztés</button>
                <button className="text-sm text-[--color-error] hover:underline">Törlés</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Orders() {
  const orders = [
    { id: '#1042', date: '2026-03-12', status: 'Szállítás', total: 11236, items: 3 },
    { id: '#1041', date: '2026-03-05', status: 'Kézbesítve', total: 8970, items: 2 },
    { id: '#1040', date: '2026-02-28', status: 'Kézbesítve', total: 15420, items: 4 },
  ];

  const statusColors: Record<string, string> = {
    'Új': 'bg-blue-100 text-blue-800',
    'Feldolgozás': 'bg-yellow-100 text-yellow-800',
    'Szállítás': 'bg-purple-100 text-purple-800',
    'Kézbesítve': 'bg-green-100 text-green-800',
  };

  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Rendeléseim</h2>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="border-b border-[--color-border]">
            <tr className="text-left">
              <th className="pb-3">Szám</th>
              <th className="pb-3">Dátum</th>
              <th className="pb-3">Állapot</th>
              <th className="pb-3">Összeg</th>
              <th className="pb-3"></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((order) => (
              <tr key={order.id} className="border-b border-[--color-border]">
                <td className="py-4 font-mono">{order.id}</td>
                <td className="py-4">{order.date}</td>
                <td className="py-4">
                  <span className={`px-2 py-1 rounded text-xs ${statusColors[order.status] || 'bg-gray-100 text-gray-800'}`}>
                    {order.status}
                  </span>
                </td>
                <td className="py-4">{formatPrice(order.total)}</td>
                <td className="py-4">
                  <button className="text-sm text-[--color-secondary] hover:underline">Részletek</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Subscriptions() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Előfizetéseim</h2>
      <div className="border border-[--color-border] rounded-lg p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <span className="inline-block px-2 py-1 bg-[--color-success] text-white text-xs rounded mb-2">Aktív</span>
            <h3 className="text-lg mb-1">Ethiopia Yirgacheffe — Szemes, 500g</h3>
            <p className="text-sm text-[--color-muted]">Naponta, Reggel (6-9)</p>
            <p className="text-sm text-[--color-muted]">Következő szállítás: 2026-03-13 (holnap)</p>
            <p className="text-lg font-semibold text-[--color-primary] mt-2">3 978 Ft/szállítás (15% kedvezmény)</p>
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="outlined">Módosítás</Button>
          <Button variant="outlined">Szüneteltetés</Button>
          <Button variant="ghost">Lemondás</Button>
        </div>
      </div>
    </div>
  );
}

function Favorites() {
  return (
    <div className="bg-white rounded-lg p-6">
      <h2 className="mb-6">Kedvenceim</h2>
      <div className="text-center py-12">
        <Heart className="w-16 h-16 mx-auto text-[--color-muted] mb-4 opacity-50" />
        <p className="text-[--color-muted]">Még nincsenek kedvenceid</p>
      </div>
    </div>
  );
}

export default function UserDashboard() {
  const location = useLocation();
  const currentPath = location.pathname.split('/').pop() || 'adataim';

  const menuItems = [
    { path: 'adataim', label: 'Adataim', icon: User },
    { path: 'cimeim', label: 'Címeim', icon: MapPin },
    { path: 'rendeleseim', label: 'Rendeléseim', icon: ShoppingBag },
    { path: 'elofizeteseim', label: 'Előfizetéseim', icon: Calendar },
    { path: 'kedvenceim', label: 'Kedvenceim', icon: Heart },
  ];

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-8">Fiókom</h1>
      <div className="grid md:grid-cols-4 gap-8">
        {/* Sidebar */}
        <aside className="bg-white rounded-lg p-6 h-fit">
          <div className="mb-6 pb-6 border-b border-[--color-border]">
            <div className="w-16 h-16 bg-[--color-background] rounded-full flex items-center justify-center mb-3">
              <User className="w-8 h-8 text-[--color-primary]" />
            </div>
            <p className="font-semibold">Kiss János</p>
          </div>
          <nav className="space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.path;
              return (
                <Link
                  key={item.path}
                  to={`/fiokom/${item.path}`}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-[--color-background] text-[--color-primary] border-l-4 border-[--color-secondary]'
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

        {/* Content */}
        <div className="md:col-span-3">
          <Routes>
            <Route index element={<Profile />} />
            <Route path="adataim" element={<Profile />} />
            <Route path="cimeim" element={<Addresses />} />
            <Route path="rendeleseim" element={<Orders />} />
            <Route path="elofizeteseim" element={<Subscriptions />} />
            <Route path="kedvenceim" element={<Favorites />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}
