import { Link } from 'react-router';
import { Facebook, Instagram } from 'lucide-react';

export function Footer() {
  return (
    <footer className="bg-[#F5F1E6] border-t border-[--color-border] mt-16">
      <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Column 1 */}
          <div>
            <h3 className="text-2xl mb-4" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
              CraftBrew
            </h3>
            <p className="text-[--color-muted] mb-4">Specialty Coffee Budapest</p>
            <p className="text-sm text-[--color-muted]">© 2026 CraftBrew</p>
          </div>

          {/* Column 2 */}
          <div>
            <h4 className="font-semibold mb-4">Linkek</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/kavek" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Kávék
                </Link>
              </li>
              <li>
                <Link to="/eszkozok" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Eszközök
                </Link>
              </li>
              <li>
                <Link to="/sztorik" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Sztorik
                </Link>
              </li>
              <li>
                <Link to="/elofizetés" className="text-[--color-muted] hover:text-[--color-secondary] transition-colors">
                  Előfizetés
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 3 */}
          <div>
            <h4 className="font-semibold mb-4">Kapcsolat</h4>
            <p className="text-[--color-muted] mb-2">
              <a href="mailto:hello@craftbrew.hu" className="hover:text-[--color-secondary] transition-colors">
                hello@craftbrew.hu
              </a>
            </p>
            <p className="text-[--color-muted] mb-4">
              CraftBrew Labor<br />
              Kazinczy u. 28<br />
              1075 Budapest
            </p>
            <div className="flex gap-3">
              <a
                href="https://facebook.com"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 bg-white rounded-full hover:bg-[--color-secondary] hover:text-white transition-colors"
              >
                <Facebook className="w-5 h-5" />
              </a>
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 bg-white rounded-full hover:bg-[--color-secondary] hover:text-white transition-colors"
              >
                <Instagram className="w-5 h-5" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}