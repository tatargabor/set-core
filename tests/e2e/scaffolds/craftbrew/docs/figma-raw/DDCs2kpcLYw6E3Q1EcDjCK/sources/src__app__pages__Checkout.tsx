import { useState } from 'react';
import { Check } from 'lucide-react';
import { Button } from '../components/Button';
import { formatPrice } from '../../lib/utils';
import { useNavigate } from 'react-router';

export default function Checkout() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    name: 'Kiss János',
    postalCode: '1052',
    city: 'Budapest',
    street: 'Váci u. 10',
    phone: '+36 20 123 4567',
    shippingMethod: 'delivery',
  });

  const orderItems = [
    { name: 'Ethiopia Yirgacheffe — Szemes, 500g', quantity: 2, price: 4680 },
    { name: 'Colombia Huila — Őrölt (filter), 250g', quantity: 1, price: 2790 },
  ];

  const subtotal = 11236;
  const shippingFee = formData.shippingMethod === 'delivery' ? 990 : 0;
  const total = subtotal + shippingFee;

  const handleComplete = () => {
    setStep(3);
  };

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Step Indicator */}
      <div className="flex items-center justify-center mb-12">
        <div className="flex items-center gap-4">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center ${
                  s < step
                    ? 'bg-[--color-primary] text-white'
                    : s === step
                    ? 'bg-[--color-primary] text-white'
                    : 'border-2 border-[--color-border] text-[--color-muted]'
                }`}
              >
                {s < step ? <Check className="w-5 h-5" /> : s}
              </div>
              <span className="ml-2 hidden sm:inline">
                {s === 1 ? 'Szállítás' : s === 2 ? 'Fizetés' : 'Megerősítés'}
              </span>
              {s < 3 && <div className="w-16 h-0.5 bg-[--color-border] mx-4" />}
            </div>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          {/* Step 1: Shipping */}
          {step === 1 && (
            <div className="bg-white rounded-lg p-6">
              <h2 className="mb-6">Szállítási cím</h2>
              <div className="space-y-4">
                <div>
                  <label className="block mb-2">Név</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block mb-2">Irányítószám</label>
                    <input
                      type="text"
                      value={formData.postalCode}
                      onChange={(e) => setFormData({ ...formData, postalCode: e.target.value })}
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                    <span className="text-xs text-[--color-success] mt-1 inline-block">Budapest</span>
                  </div>
                  <div>
                    <label className="block mb-2">Város</label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                  </div>
                </div>
                <div>
                  <label className="block mb-2">Utca, házszám</label>
                  <input
                    type="text"
                    value={formData.street}
                    onChange={(e) => setFormData({ ...formData, street: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>
                <div>
                  <label className="block mb-2">Telefonszám</label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>

                <div className="mt-6">
                  <h3 className="font-semibold mb-4">Szállítási mód</h3>
                  <label className="flex items-center gap-3 p-4 border border-[--color-border] rounded-lg mb-3 cursor-pointer hover:bg-[--color-background]">
                    <input
                      type="radio"
                      name="shipping"
                      value="delivery"
                      checked={formData.shippingMethod === 'delivery'}
                      onChange={(e) => setFormData({ ...formData, shippingMethod: e.target.value })}
                    />
                    <div className="flex-1">
                      <p className="font-medium">Házhozszállítás</p>
                      <p className="text-sm text-[--color-muted]">990 Ft — Holnap (Budapest)</p>
                    </div>
                  </label>
                  <label className="flex items-center gap-3 p-4 border border-[--color-border] rounded-lg cursor-pointer hover:bg-[--color-background]">
                    <input
                      type="radio"
                      name="shipping"
                      value="pickup"
                      checked={formData.shippingMethod === 'pickup'}
                      onChange={(e) => setFormData({ ...formData, shippingMethod: e.target.value })}
                    />
                    <div className="flex-1">
                      <p className="font-medium">Személyes átvétel</p>
                      <p className="text-sm text-[--color-muted]">
                        Ingyenes — CraftBrew Labor, Kazinczy u. 28
                      </p>
                    </div>
                  </label>
                  <p className="text-sm text-[--color-success] mt-3">
                    💚 Ingyenes szállítás 15 000 Ft felett (Budapest)
                  </p>
                </div>

                <Button variant="primary" fullWidth onClick={() => setStep(2)} className="mt-6">
                  Tovább
                </Button>
              </div>
            </div>
          )}

          {/* Step 2: Payment */}
          {step === 2 && (
            <div className="bg-white rounded-lg p-6">
              <h2 className="mb-6">Fizetés</h2>
              <div className="space-y-4">
                <div>
                  <label className="block mb-2">Kártyaszám</label>
                  <input
                    type="text"
                    placeholder="1234 5678 9012 3456"
                    className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block mb-2">Lejárat</label>
                    <input
                      type="text"
                      placeholder="MM/ÉÉ"
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                  </div>
                  <div>
                    <label className="block mb-2">CVC</label>
                    <input
                      type="text"
                      placeholder="123"
                      className="w-full border border-[--color-border] rounded-lg px-4 py-3"
                    />
                  </div>
                </div>
                <Button variant="primary" fullWidth onClick={handleComplete} className="mt-6">
                  Fizetek — {formatPrice(total)}
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: Confirmation */}
          {step === 3 && (
            <div className="bg-white rounded-lg p-8 text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Check className="w-10 h-10 text-[--color-success]" />
              </div>
              <h2 className="mb-4">Köszönjük a rendelésed!</h2>
              <p className="text-[--color-muted] mb-6">
                Rendelésszám: <span className="font-mono font-bold text-[--color-text]">#1042</span>
              </p>
              <div className="text-left max-w-md mx-auto mb-6 space-y-2">
                <p>
                  <strong>Szállítási cím:</strong>
                </p>
                <p className="text-[--color-muted]">
                  {formData.name}
                  <br />
                  {formData.postalCode} {formData.city}, {formData.street}
                </p>
                <p className="mt-4">
                  <strong>Várható kézbesítés:</strong> Holnap
                </p>
              </div>
              <div className="flex gap-4 justify-center">
                <Button variant="outlined" onClick={() => navigate('/fiokom/rendeleseim')}>
                  Rendeléseim
                </Button>
                <Button variant="primary" onClick={() => navigate('/')}>
                  Vissza a főoldalra
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Order Summary */}
        <div className="bg-white rounded-lg p-6 h-fit sticky top-24">
          <h3 className="font-semibold mb-6">Rendelés összegzése</h3>
          <div className="space-y-3 mb-6">
            {orderItems.map((item, idx) => (
              <div key={idx} className="flex justify-between text-sm">
                <span className="text-[--color-muted]">
                  {item.name} x{item.quantity}
                </span>
                <span>{formatPrice(item.price * item.quantity)}</span>
              </div>
            ))}
            <div className="border-t border-[--color-border] pt-3">
              <div className="flex justify-between">
                <span className="text-[--color-muted]">Részösszeg</span>
                <span>{formatPrice(subtotal)}</span>
              </div>
              <div className="flex justify-between mt-2">
                <span className="text-[--color-muted]">Szállítás</span>
                <span>{shippingFee > 0 ? formatPrice(shippingFee) : 'Ingyenes'}</span>
              </div>
            </div>
            <div className="border-t border-[--color-border] pt-3">
              <div className="flex justify-between text-xl font-bold">
                <span>Összesen</span>
                <span className="text-[--color-primary]">{formatPrice(total)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
