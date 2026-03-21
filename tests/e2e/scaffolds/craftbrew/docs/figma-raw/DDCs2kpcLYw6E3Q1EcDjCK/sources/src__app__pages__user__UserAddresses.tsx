import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart, Plus, Edit2, Trash2, Star, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Address {
  id: string;
  label: string;
  name: string;
  postalCode: string;
  city: string;
  street: string;
  phone: string;
  zone: string;
  isDefault: boolean;
}

export default function UserAddresses() {
  const location = useLocation();
  const [addresses, setAddresses] = useState<Address[]>([
    {
      id: '1',
      label: 'Otthon',
      name: 'Nagy Petra',
      postalCode: '1075',
      city: 'Budapest',
      street: 'Kazinczy u. 28.',
      phone: '+36 30 123 4567',
      zone: 'Budapest',
      isDefault: true,
    },
    {
      id: '2',
      label: 'Iroda',
      name: 'Nagy Petra',
      postalCode: '1061',
      city: 'Budapest',
      street: 'Andrássy út 45.',
      phone: '+36 30 123 4567',
      zone: 'Budapest',
      isDefault: false,
    },
  ]);

  const [isEditing, setIsEditing] = useState(false);

  const menuItems = [
    { id: 'adataim', label: 'Adataim', icon: User, path: '/fiokom' },
    { id: 'cimeim', label: 'Címeim', icon: MapPin, path: '/fiokom/cimeim' },
    { id: 'rendeleseim', label: 'Rendeléseim', icon: ShoppingBag, path: '/fiokom/rendeleseim' },
    { id: 'elofizeteseim', label: 'Előfizetéseim', icon: Calendar, path: '/fiokom/elofizeteseim' },
    { id: 'kedvenceim', label: 'Kedvenceim', icon: Heart, path: '/fiokom/kedvenceim' },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] py-12">
      <div className="max-w-[1280px] mx-auto px-4 sm:px-6">
        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar */}
          <aside className="hidden md:block w-64 shrink-0">
            <div className="bg-white rounded-lg p-6 shadow-sm">
              <div className="flex flex-col items-center mb-6">
                <div className="w-20 h-20 bg-[--color-background] rounded-full flex items-center justify-center mb-3">
                  <User className="w-10 h-10 text-[--color-muted]" />
                </div>
                <h3 className="font-semibold">Nagy Petra</h3>
                <p className="text-sm text-[--color-muted]">nagy.petra@email.com</p>
              </div>
              <nav className="space-y-1">
                {menuItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.id}
                      to={item.path}
                      className={`flex items-center gap-3 px-4 py-3 rounded-md transition-colors ${
                        isActive
                          ? 'bg-[--color-primary] text-white'
                          : 'text-[--color-text] hover:bg-[--color-background]'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          </aside>

          {/* Main Content */}
          <main className="flex-1">
            <div className="bg-white rounded-lg p-6 md:p-8 shadow-sm">
              <div className="flex items-center justify-between mb-6">
                <h1>Címeim</h1>
                <Button onClick={() => setIsEditing(true)}>
                  <Plus className="w-5 h-5 mr-2" />
                  Új cím
                </Button>
              </div>

              {/* Address Cards */}
              <div className="grid gap-4 md:grid-cols-2">
                {addresses.map((address) => (
                  <div
                    key={address.id}
                    className="border border-[--color-border] rounded-lg p-6 relative hover:border-[--color-secondary] transition-colors"
                  >
                    {address.isDefault && (
                      <div className="absolute top-4 right-4">
                        <Star className="w-5 h-5 text-[--color-secondary] fill-current" />
                      </div>
                    )}
                    <div className="mb-4">
                      <span className="inline-block px-3 py-1 bg-[--color-secondary] text-white text-xs rounded-full mb-2">
                        {address.label}
                      </span>
                      {address.zone && (
                        <span className="inline-block ml-2 px-3 py-1 bg-[--color-background] text-[--color-primary] text-xs rounded-full">
                          {address.zone}
                        </span>
                      )}
                    </div>
                    <p className="font-medium mb-1">{address.name}</p>
                    <p className="text-[--color-muted] text-sm mb-1">
                      {address.postalCode} {address.city}
                    </p>
                    <p className="text-[--color-muted] text-sm mb-1">{address.street}</p>
                    <p className="text-[--color-muted] text-sm mb-4">{address.phone}</p>

                    <div className="flex gap-2 text-sm">
                      <button className="text-[--color-secondary] hover:underline">Szerkesztés</button>
                      <span className="text-[--color-border]">|</span>
                      <button className="text-[--color-error] hover:underline">Törlés</button>
                      {!address.isDefault && (
                        <>
                          <span className="text-[--color-border]">|</span>
                          <button className="text-[--color-secondary] hover:underline">Alapértelmezett</button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </main>
        </div>
      </div>

      {/* Add/Edit Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-lg">
            <div className="border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új cím hozzáadása</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block mb-2 font-medium">Címke</label>
                <input
                  type="text"
                  placeholder="Otthon, Iroda, Szülők..."
                  className="w-full px-4 py-2 border border-[--color-border] rounded-md"
                />
              </div>

              <div>
                <label className="block mb-2 font-medium">Név</label>
                <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Irányítószám</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  <p className="text-sm text-[--color-muted] mt-1">
                    <span className="inline-block px-2 py-0.5 bg-[--color-secondary] text-white text-xs rounded">
                      Budapest
                    </span>
                  </p>
                </div>
                <div>
                  <label className="block mb-2 font-medium">Város</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Utca, házszám</label>
                <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div>
                <label className="block mb-2 font-medium">Telefon</label>
                <input type="tel" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>
            </div>

            <div className="border-t border-[--color-border] p-6 flex justify-end gap-3">
              <Button variant="outlined" onClick={() => setIsEditing(false)}>
                Mégse
              </Button>
              <Button variant="primary">Mentés</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
