import { useState } from 'react';
import { Link } from 'react-router';
import { Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/Button';

export default function Register() {
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    language: 'HU',
    acceptTerms: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle registration
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="w-full max-w-md bg-white rounded-lg p-8 shadow-lg">
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold" style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)' }}>
            CraftBrew
          </h2>
        </div>

        <h2 className="mb-6">Regisztráció</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block mb-2">Teljes név</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full border border-[--color-border] rounded-lg px-4 py-3"
              required
            />
          </div>

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
            <p className="text-xs text-[--color-muted] mt-1">Minimum 8 karakter</p>
          </div>

          <div>
            <label className="block mb-2">Jelszó megerősítése</label>
            <div className="relative">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                className="w-full border border-[--color-border] rounded-lg px-4 py-3 pr-12"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[--color-muted]"
              >
                {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block mb-2">Nyelv</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="language"
                  value="HU"
                  checked={formData.language === 'HU'}
                  onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                />
                <span>HU</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="language"
                  value="EN"
                  checked={formData.language === 'EN'}
                  onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                />
                <span>EN</span>
              </label>
            </div>
          </div>

          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={formData.acceptTerms}
              onChange={(e) => setFormData({ ...formData, acceptTerms: e.target.checked })}
              className="w-4 h-4 mt-1 rounded border-[--color-border]"
              required
            />
            <span className="text-sm">
              Elfogadom az{' '}
              <a href="#" className="text-[--color-secondary] underline">
                ÁSZF-et
              </a>{' '}
              és az{' '}
              <a href="#" className="text-[--color-secondary] underline">
                Adatvédelmi szabályzatot
              </a>
            </span>
          </label>

          <Button type="submit" variant="primary" fullWidth>
            Regisztráció
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-[--color-muted]">
            Van már fiókod?{' '}
            <Link to="/belepes" className="text-[--color-secondary] hover:underline">
              Bejelentkezés
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
