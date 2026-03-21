import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import { User, MapPin, ShoppingBag, Calendar, Heart, Lock } from 'lucide-react';
import { Button } from '../../components/Button';

export default function UserProfile() {
  const location = useLocation();
  const [language, setLanguage] = useState('hu');

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
          {/* Sidebar - Desktop */}
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

          {/* Mobile Menu Tabs */}
          <div className="md:hidden overflow-x-auto">
            <div className="flex gap-2 pb-2">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.id}
                    to={item.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md whitespace-nowrap transition-colors ${
                      isActive
                        ? 'bg-[--color-primary] text-white'
                        : 'bg-white text-[--color-text] border border-[--color-border]'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-sm">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Main Content */}
          <main className="flex-1">
            <div className="bg-white rounded-lg p-6 md:p-8 shadow-sm">
              <h1 className="mb-6">Adataim</h1>

              <form className="space-y-6">
                <div>
                  <label className="block mb-2 font-medium">Név</label>
                  <input
                    type="text"
                    defaultValue="Nagy Petra"
                    className="w-full px-4 py-2 border border-[--color-border] rounded-md"
                  />
                </div>

                <div>
                  <label className="block mb-2 font-medium">Email cím</label>
                  <div className="relative">
                    <input
                      type="email"
                      defaultValue="nagy.petra@email.com"
                      readOnly
                      className="w-full px-4 py-2 pr-10 border border-[--color-border] rounded-md bg-[--color-background]"
                    />
                    <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
                  </div>
                  <p className="text-sm text-[--color-muted] mt-1">
                    Az email címed megváltoztatásához lépj kapcsolatba az ügyfélszolgálattal.
                  </p>
                </div>

                <div>
                  <label className="block mb-2 font-medium">Nyelv</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="language"
                        value="hu"
                        checked={language === 'hu'}
                        onChange={(e) => setLanguage(e.target.value)}
                        className="w-4 h-4"
                      />
                      <span>Magyar</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="language"
                        value="en"
                        checked={language === 'en'}
                        onChange={(e) => setLanguage(e.target.value)}
                        className="w-4 h-4"
                      />
                      <span>English</span>
                    </label>
                  </div>
                </div>

                <Button variant="primary">Mentés</Button>
              </form>

              {/* Password Change Section */}
              <div className="border-t border-[--color-border] mt-8 pt-8">
                <h2 className="mb-6">Jelszó módosítása</h2>
                <form className="space-y-4 max-w-md">
                  <div>
                    <label className="block mb-2 font-medium">Jelenlegi jelszó</label>
                    <input type="password" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>
                  <div>
                    <label className="block mb-2 font-medium">Új jelszó</label>
                    <input type="password" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>
                  <div>
                    <label className="block mb-2 font-medium">Új jelszó megerősítése</label>
                    <input type="password" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>
                  <Button variant="outlined">Módosítás</Button>
                </form>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
