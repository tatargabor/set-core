import { useState } from 'react';
import { Link } from 'react-router';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/Button';

export default function Login() {
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    remember: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle login
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md bg-white rounded-lg p-8 shadow-lg">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
            CraftBrew
          </h2>
        </div>

        <h2 className="mb-6">Bejelentkezés</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-2">Email</label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3"
              required
            />
          </div>

          <div>
            <label className="block mb-2">Jelszó</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full border border-[--color-border] rounded-lg px-4 py-3 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[--color-muted]"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.remember}
                onChange={(e) => setFormData({ ...formData, remember: e.target.checked })}
                className="w-4 h-4 rounded border-[--color-border]"
              />
              <span className="text-sm">Emlékezz rám</span>
            </label>
            <Link to="/jelszo-elfelejtve" className="text-sm text-[--color-secondary] hover:underline">
              Elfelejtett jelszó?
            </Link>
          </div>

          <Button type="submit" variant="primary" fullWidth>
            Bejelentkezés
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-[--color-muted] mb-3">Nincs még fiókod?</p>
          <Link to="/regisztracio">
            <Button variant="outlined" fullWidth>
              Regisztráció
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
