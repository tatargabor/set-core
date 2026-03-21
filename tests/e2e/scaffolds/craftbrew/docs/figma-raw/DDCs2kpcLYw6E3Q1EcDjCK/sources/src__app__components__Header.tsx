import { useState } from 'react';
import { Link } from 'react-router';
import { Search, ShoppingCart, Menu, X, User } from 'lucide-react';

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [cartCount] = useState(3);

  return (
    <>
      {/* Desktop Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-[--color-border] shadow-sm">
        <div className="max-w-[--container-max] mx-auto px-4 sm:px-6">
          {/* Desktop */}
          <div className="hidden md:flex items-center justify-between h-20">
            {/* Logo */}
            <Link to="/" className="text-2xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-8">
              <Link to="/kavek" className="hover:text-[--color-secondary] transition-colors">
                Kávék
              </Link>
              <Link to="/eszkozok" className="hover:text-[--color-secondary] transition-colors">
                Eszközök
              </Link>
              <Link to="/sztorik" className="hover:text-[--color-secondary] transition-colors">
                Sztorik
              </Link>
              <Link to="/elofizetés" className="hover:text-[--color-secondary] transition-colors">
                Előfizetés
              </Link>
            </nav>

            {/* Right Icons */}
            <div className="flex items-center gap-4">
              <button className="p-2 hover:text-[--color-secondary] transition-colors">
                <Search className="w-5 h-5" />
              </button>
              <Link to="/kosar" className="relative p-2 hover:text-[--color-secondary] transition-colors">
                <ShoppingCart className="w-5 h-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[--color-error] text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount}
                  </span>
                )}
              </Link>
              <button className="px-3 py-1 text-sm hover:text-[--color-secondary] transition-colors">
                EN
              </button>
              <Link to="/fiokom" className="p-2 hover:text-[--color-secondary] transition-colors">
                <User className="w-5 h-5" />
              </Link>
            </div>
          </div>

          {/* Mobile */}
          <div className="md:hidden flex items-center justify-between h-14">
            <button onClick={() => setMobileMenuOpen(true)} className="p-2">
              <Menu className="w-6 h-6" />
            </button>
            <Link to="/" className="text-xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </Link>
            <div className="flex items-center gap-2">
              <button className="p-2">
                <Search className="w-5 h-5" />
              </button>
              <Link to="/kosar" className="relative p-2">
                <ShoppingCart className="w-5 h-5" />
                {cartCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-[--color-error] text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {cartCount}
                  </span>
                )}
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <div className="absolute left-0 top-0 bottom-0 w-80 max-w-[85vw] bg-white shadow-xl">
            <div className="p-4 border-b border-[--color-border]">
              <button onClick={() => setMobileMenuOpen(false)} className="p-2">
                <X className="w-6 h-6" />
              </button>
            </div>
            <nav className="flex flex-col">
              <Link
                to="/kavek"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Kávék
              </Link>
              <Link
                to="/eszkozok"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Eszközök
              </Link>
              <Link
                to="/sztorik"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sztorik
              </Link>
              <Link
                to="/elofizetés"
                className="px-6 py-4 hover:bg-[--color-background] transition-colors border-b border-[--color-border]"
                onClick={() => setMobileMenuOpen(false)}
              >
                Előfizetés
              </Link>
              <div className="mt-4 px-6 py-4 border-t border-[--color-border]">
                <Link
                  to="/kosar"
                  className="block py-3 hover:text-[--color-secondary]"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Kosár ({cartCount})
                </Link>
                <Link
                  to="/fiokom"
                  className="block py-3 hover:text-[--color-secondary]"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  Fiókom
                </Link>
                <button className="block py-3 hover:text-[--color-secondary]">
                  EN
                </button>
              </div>
            </nav>
          </div>
        </div>
      )}
    </>
  );
}