import { useState } from 'react';
import { Link } from 'react-router';
import { Trash2, Minus, Plus, ShoppingBag } from 'lucide-react';
import { Button } from '../components/Button';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { formatPrice } from '../../lib/utils';

export default function Cart() {
  const [cartItems, setCartItems] = useState([
    {
      id: '1',
      productId: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      variant: 'Szemes, 500g',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=200',
      price: 4680,
      quantity: 2,
    },
    {
      id: '2',
      productId: 'colombia-huila',
      name: 'Colombia Huila',
      variant: 'Őrölt (filter), 250g',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=200',
      price: 2790,
      quantity: 1,
    },
    {
      id: '3',
      productId: 'v60-dripper',
      name: 'Hario V60 Dripper',
      variant: 'Fehér',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=200',
      price: 3990,
      quantity: 1,
    },
  ]);

  const [couponCode, setCouponCode] = useState('');
  const [appliedCoupon, setAppliedCoupon] = useState<{ code: string; discount: number } | null>(null);
  const [giftCardCode, setGiftCardCode] = useState('');
  const [appliedGiftCard, setAppliedGiftCard] = useState<{ code: string; amount: number } | null>(null);

  const updateQuantity = (id: string, newQuantity: number) => {
    if (newQuantity < 1) return;
    setCartItems(cartItems.map((item) => (item.id === id ? { ...item, quantity: newQuantity } : item)));
  };

  const removeItem = (id: string) => {
    setCartItems(cartItems.filter((item) => item.id !== id));
  };

  const applyCoupon = () => {
    if (couponCode.toUpperCase() === 'ELSO10') {
      setAppliedCoupon({ code: 'ELSO10', discount: 0.1 });
      setCouponCode('');
    }
  };

  const applyGiftCard = () => {
    if (giftCardCode.startsWith('GC-')) {
      setAppliedGiftCard({ code: giftCardCode, amount: 5000 });
      setGiftCardCode('');
    }
  };

  const subtotal = cartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const discount = appliedCoupon ? subtotal * appliedCoupon.discount : 0;
  const giftCardDeduction = appliedGiftCard ? Math.min(appliedGiftCard.amount, subtotal - discount) : 0;
  const total = subtotal - discount - giftCardDeduction;

  if (cartItems.length === 0) {
    return (
      <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-16">
        <div className="text-center py-16">
          <ShoppingBag className="w-24 h-24 mx-auto text-[--color-muted] mb-6" />
          <h2 className="mb-4">A kosarad üres</h2>
          <Link to="/kavek" className="text-[--color-secondary] hover:underline font-medium">
            Fedezd fel kávéinkat →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-8">Kosár</h1>

      <div className="grid md:grid-cols-3 gap-8">
        {/* Cart Items */}
        <div className="md:col-span-2">
          <div className="bg-white rounded-lg overflow-hidden">
            {/* Desktop Table */}
            <div className="hidden md:block">
              <table className="w-full">
                <thead className="border-b border-[--color-border]">
                  <tr className="text-left text-sm text-[--color-muted]">
                    <th className="p-4">Termék</th>
                    <th className="p-4">Egységár</th>
                    <th className="p-4">Mennyiség</th>
                    <th className="p-4">Összesen</th>
                    <th className="p-4"></th>
                  </tr>
                </thead>
                <tbody>
                  {cartItems.map((item) => (
                    <tr key={item.id} className="border-b border-[--color-border]">
                      <td className="p-4">
                        <div className="flex items-center gap-4">
                          <ImageWithFallback
                            src={item.image}
                            alt={item.name}
                            className="w-16 h-16 object-cover rounded"
                          />
                          <div>
                            <p className="font-medium">{item.name}</p>
                            <p className="text-sm text-[--color-muted]">{item.variant}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">{formatPrice(item.price)}</td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => updateQuantity(item.id, item.quantity - 1)}
                            className="w-11 h-11 border border-[--color-border] rounded flex items-center justify-center hover:bg-[--color-background]"
                          >
                            <Minus className="w-4 h-4" />
                          </button>
                          <span className="w-12 text-center">{item.quantity}</span>
                          <button
                            onClick={() => updateQuantity(item.id, item.quantity + 1)}
                            className="w-11 h-11 border border-[--color-border] rounded flex items-center justify-center hover:bg-[--color-background]"
                          >
                            <Plus className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                      <td className="p-4 font-semibold">{formatPrice(item.price * item.quantity)}</td>
                      <td className="p-4">
                        <button
                          onClick={() => removeItem(item.id)}
                          className="p-2 text-[--color-error] hover:bg-red-50 rounded"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden space-y-4 p-4">
              {cartItems.map((item) => (
                <div key={item.id} className="flex gap-4 pb-4 border-b border-[--color-border]">
                  <ImageWithFallback src={item.image} alt={item.name} className="w-20 h-20 object-cover rounded" />
                  <div className="flex-1">
                    <p className="font-medium mb-1">{item.name}</p>
                    <p className="text-sm text-[--color-muted] mb-2">{item.variant}</p>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => updateQuantity(item.id, item.quantity - 1)}
                          className="w-9 h-9 border border-[--color-border] rounded flex items-center justify-center"
                        >
                          <Minus className="w-3 h-3" />
                        </button>
                        <span className="w-8 text-center">{item.quantity}</span>
                        <button
                          onClick={() => updateQuantity(item.id, item.quantity + 1)}
                          className="w-9 h-9 border border-[--color-border] rounded flex items-center justify-center"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="font-semibold">{formatPrice(item.price * item.quantity)}</p>
                    </div>
                  </div>
                  <button onClick={() => removeItem(item.id)} className="p-2 text-[--color-error]">
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Coupon */}
          <div className="bg-white rounded-lg p-6 mt-6">
            <h3 className="font-semibold mb-4">Kuponkód</h3>
            {appliedCoupon ? (
              <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg p-3">
                <span className="text-sm">
                  <strong>{appliedCoupon.code}</strong> — {appliedCoupon.discount * 100}% kedvezmény
                </span>
                <button onClick={() => setAppliedCoupon(null)} className="text-sm text-[--color-error]">
                  ✕
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value)}
                  placeholder="Kuponkód"
                  className="flex-1 border border-[--color-border] rounded-lg px-4 py-2"
                />
                <Button variant="outlined" onClick={applyCoupon}>
                  Beváltás
                </Button>
              </div>
            )}
          </div>

          {/* Gift Card */}
          <div className="bg-white rounded-lg p-6 mt-4">
            <h3 className="font-semibold mb-4">Ajándékkártya</h3>
            {appliedGiftCard ? (
              <div className="flex items-center justify-between bg-green-50 border border-green-200 rounded-lg p-3">
                <span className="text-sm">
                  <strong>{appliedGiftCard.code}</strong> — Levonva: {formatPrice(giftCardDeduction)}
                </span>
                <button onClick={() => setAppliedGiftCard(null)} className="text-sm text-[--color-error]">
                  ✕
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={giftCardCode}
                  onChange={(e) => setGiftCardCode(e.target.value)}
                  placeholder="Ajándékkártya kód"
                  className="flex-1 border border-[--color-border] rounded-lg px-4 py-2"
                />
                <Button variant="outlined" onClick={applyGiftCard}>
                  Beváltás
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Order Summary */}
        <div className="bg-white rounded-lg p-6 h-fit sticky top-24">
          <h3 className="font-semibold mb-6">Rendelés összegzése</h3>
          <div className="space-y-3 mb-6">
            <div className="flex justify-between">
              <span className="text-[--color-muted]">Részösszeg</span>
              <span>{formatPrice(subtotal)}</span>
            </div>
            {appliedCoupon && (
              <div className="flex justify-between text-[--color-error]">
                <span>Kedvezmény ({appliedCoupon.code})</span>
                <span>-{formatPrice(discount)}</span>
              </div>
            )}
            {appliedGiftCard && (
              <div className="flex justify-between text-[--color-error]">
                <span>Ajándékkártya</span>
                <span>-{formatPrice(giftCardDeduction)}</span>
              </div>
            )}
            <div className="flex justify-between text-[--color-muted]">
              <span>Szállítás</span>
              <span>Pénztárnál számítjuk</span>
            </div>
            <div className="border-t border-[--color-border] pt-3">
              <div className="flex justify-between text-xl font-bold">
                <span>Összesen</span>
                <span className="text-[--color-primary]">{formatPrice(total)}</span>
              </div>
            </div>
          </div>
          <Link to="/penztar">
            <Button variant="primary" fullWidth>
              Tovább a pénztárhoz
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
