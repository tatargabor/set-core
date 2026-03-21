import { useState } from 'react';
import { Button } from '../components/Button';
import { ProductCard } from '../components/ProductCard';
import { Check } from 'lucide-react';

export default function SubscriptionWizard() {
  const [step, setStep] = useState(1);
  const [selectedCoffee, setSelectedCoffee] = useState('');
  const [selectedSize, setSelectedSize] = useState('500g');
  const [selectedFrequency, setSelectedFrequency] = useState('daily');

  const coffees = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=400',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
    },
  ];

  const frequencies = [
    { id: 'daily', name: 'Naponta', discount: 15, badge: 'Legjobb ár!' },
    { id: 'weekly', name: 'Hetente (hétfő)', discount: 10 },
    { id: 'biweekly', name: 'Kéthetente', discount: 7 },
    { id: 'monthly', name: 'Havonta', discount: 5 },
  ];

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Progress Bar */}
      <div className="mb-12">
        <div className="flex items-center justify-between max-w-3xl mx-auto">
          {[1, 2, 3, 4, 5].map((s) => (
            <div key={s} className="flex items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  s <= step ? 'bg-[--color-primary] text-white' : 'bg-[--color-border] text-[--color-muted]'
                }`}
              >
                {s < step ? <Check className="w-5 h-5" /> : s}
              </div>
              {s < 5 && (
                <div
                  className={`flex-1 h-1 mx-2 ${
                    s < step ? 'bg-[--color-primary]' : 'bg-[--color-border]'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="max-w-4xl mx-auto">
        {/* Step 1: Choose Coffee */}
        {step === 1 && (
          <div>
            <h2 className="mb-8 text-center">Válaszd ki a kávédat</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              {coffees.map((coffee) => (
                <div
                  key={coffee.id}
                  onClick={() => setSelectedCoffee(coffee.id)}
                  className={`cursor-pointer ${
                    selectedCoffee === coffee.id ? 'ring-2 ring-[--color-secondary] rounded-lg' : ''
                  }`}
                >
                  <ProductCard {...coffee} />
                </div>
              ))}
            </div>
            <div className="flex justify-center">
              <Button variant="primary" onClick={() => setStep(2)} disabled={!selectedCoffee}>
                Tovább
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Size */}
        {step === 2 && (
          <div>
            <h2 className="mb-8 text-center">Forma és méret</h2>
            <div className="max-w-md mx-auto space-y-4 mb-8">
              <div>
                <label className="block mb-2 font-medium">Forma</label>
                <select className="w-full border border-[--color-border] rounded-lg px-4 py-3 bg-white">
                  <option>Szemes</option>
                  <option>Őrölt (filter)</option>
                  <option>Őrölt (eszpresszó)</option>
                </select>
              </div>

              <div>
                <label className="block mb-3 font-medium">Méret</label>
                {['250g', '500g', '1kg'].map((size) => (
                  <label
                    key={size}
                    className={`flex items-center justify-between p-4 border-2 rounded-lg mb-3 cursor-pointer ${
                      selectedSize === size ? 'border-[--color-secondary] bg-[--color-background]' : 'border-[--color-border]'
                    }`}
                  >
                    <input
                      type="radio"
                      name="size"
                      value={size}
                      checked={selectedSize === size}
                      onChange={(e) => setSelectedSize(e.target.value)}
                      className="mr-3"
                    />
                    <span className="flex-1">{size}</span>
                    <span className="font-semibold">
                      {size === '250g' ? '2 490 Ft' : size === '500g' ? '4 680 Ft' : '6 580 Ft'}
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-center gap-4">
              <Button variant="outlined" onClick={() => setStep(1)}>
                Vissza
              </Button>
              <Button variant="primary" onClick={() => setStep(3)}>
                Tovább
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Frequency */}
        {step === 3 && (
          <div>
            <h2 className="mb-8 text-center">Gyakoriság</h2>
            <div className="max-w-2xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
              {frequencies.map((freq) => (
                <label
                  key={freq.id}
                  className={`relative p-6 border-2 rounded-lg cursor-pointer ${
                    selectedFrequency === freq.id
                      ? 'border-[--color-secondary] bg-[--color-background]'
                      : 'border-[--color-border]'
                  }`}
                >
                  <input
                    type="radio"
                    name="frequency"
                    value={freq.id}
                    checked={selectedFrequency === freq.id}
                    onChange={(e) => setSelectedFrequency(e.target.value)}
                    className="sr-only"
                  />
                  {freq.badge && (
                    <span className="absolute top-3 right-3 px-2 py-1 bg-[--color-success] text-white text-xs rounded">
                      {freq.badge}
                    </span>
                  )}
                  <h3 className="text-xl mb-2">{freq.name}</h3>
                  <p className="text-2xl font-bold text-[--color-primary] mb-1">-{freq.discount}%</p>
                  <p className="text-sm text-[--color-muted]">
                    {Math.round(4680 * (1 - freq.discount / 100))} Ft / szállítás
                  </p>
                </label>
              ))}
            </div>
            <div className="flex justify-center gap-4">
              <Button variant="outlined" onClick={() => setStep(2)}>
                Vissza
              </Button>
              <Button variant="primary" onClick={() => setStep(4)}>
                Tovább
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Delivery Details */}
        {step === 4 && (
          <div>
            <h2 className="mb-8 text-center">Kiszállítás</h2>
            <div className="max-w-md mx-auto space-y-6 mb-8">
              <div>
                <label className="block mb-3 font-medium">Időablak</label>
                <div className="space-y-3">
                  {['Reggel (6-9)', 'Délelőtt (9-12)', 'Délután (14-17)'].map((time) => (
                    <label
                      key={time}
                      className="flex items-center gap-3 p-4 border border-[--color-border] rounded-lg cursor-pointer hover:bg-[--color-background]"
                    >
                      <input type="radio" name="time" />
                      <span>{time}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Szállítási cím</label>
                <input
                  type="text"
                  placeholder="Irányítószám"
                  className="w-full border border-[--color-border] rounded-lg px-4 py-3 mb-3"
                />
                <input
                  type="text"
                  placeholder="Város"
                  className="w-full border border-[--color-border] rounded-lg px-4 py-3 mb-3"
                />
                <input
                  type="text"
                  placeholder="Utca, házszám"
                  className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                />
              </div>

              <div>
                <label className="block mb-2 font-medium">Kezdő dátum</label>
                <input
                  type="date"
                  className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                />
              </div>
            </div>
            <div className="flex justify-center gap-4">
              <Button variant="outlined" onClick={() => setStep(3)}>
                Vissza
              </Button>
              <Button variant="primary" onClick={() => setStep(5)}>
                Tovább
              </Button>
            </div>
          </div>
        )}

        {/* Step 5: Summary */}
        {step === 5 && (
          <div>
            <h2 className="mb-8 text-center">Összegzés</h2>
            <div className="max-w-lg mx-auto bg-white rounded-lg p-8">
              <div className="mb-6">
                <h3 className="font-semibold mb-4">Kiválasztott kávé</h3>
                <p className="text-[--color-muted]">Ethiopia Yirgacheffe — Szemes, 500g</p>
              </div>

              <div className="mb-6">
                <h3 className="font-semibold mb-4">Szállítás részletei</h3>
                <p className="text-[--color-muted]">Naponta, Reggel (6-9)</p>
                <p className="text-[--color-muted]">1052 Budapest, Váci u. 10</p>
                <p className="text-[--color-muted]">Kezdés: 2026-03-13</p>
              </div>

              <div className="border-t border-[--color-border] pt-6 mb-6">
                <div className="flex justify-between mb-2">
                  <span className="text-[--color-muted]">Alapár</span>
                  <span>4 680 Ft</span>
                </div>
                <div className="flex justify-between mb-2 text-[--color-success]">
                  <span>Kedvezmény (15%)</span>
                  <span>-702 Ft</span>
                </div>
                <div className="flex justify-between mb-2">
                  <span className="text-[--color-muted]">Szállítás</span>
                  <span>990 Ft</span>
                </div>
                <div className="flex justify-between text-xl font-bold pt-3 border-t border-[--color-border]">
                  <span>Összesen</span>
                  <span className="text-[--color-primary]">4 968 Ft / szállítás</span>
                </div>
              </div>

              <Button variant="primary" fullWidth>
                Előfizetés indítása
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
