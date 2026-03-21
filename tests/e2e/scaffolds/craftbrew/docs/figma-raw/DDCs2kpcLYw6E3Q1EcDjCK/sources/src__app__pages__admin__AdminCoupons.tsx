import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Coupon {
  id: string;
  code: string;
  type: '%' | 'Ft';
  value: number;
  category: string;
  expiry: string;
  used: number;
  maxUses: number;
  active: boolean;
}

export default function AdminCoupons() {
  const [isEditing, setIsEditing] = useState(false);

  const coupons: Coupon[] = [
    {
      id: '1',
      code: 'ELSO10',
      type: '%',
      value: 10,
      category: 'Minden',
      expiry: '—',
      used: 124,
      maxUses: 0,
      active: true,
    },
    {
      id: '2',
      code: 'NYAR2026',
      type: '%',
      value: 15,
      category: 'Minden',
      expiry: '2026-08-31',
      used: 87,
      maxUses: 500,
      active: true,
    },
    {
      id: '3',
      code: 'BUNDLE20',
      type: '%',
      value: 20,
      category: 'Csomagok',
      expiry: '—',
      used: 42,
      maxUses: 0,
      active: true,
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Kuponok</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új kupon
          </Button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kód</th>
                <th className="text-left p-4 font-semibold">Típus</th>
                <th className="text-left p-4 font-semibold">Érték</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Lejárat</th>
                <th className="text-left p-4 font-semibold">Felhasználás</th>
                <th className="text-left p-4 font-semibold">Aktív</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map((coupon) => (
                <tr key={coupon.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-semibold" style={{ fontFamily: 'var(--font-mono)' }}>
                    {coupon.code}
                  </td>
                  <td className="p-4">{coupon.type === '%' ? 'Százalék' : 'Fix összeg'}</td>
                  <td className="p-4 font-medium">
                    {coupon.value}
                    {coupon.type}
                  </td>
                  <td className="p-4 text-[--color-muted]">{coupon.category}</td>
                  <td className="p-4 text-[--color-muted]">{coupon.expiry}</td>
                  <td className="p-4">
                    {coupon.used} / {coupon.maxUses === 0 ? '∞' : coupon.maxUses}
                  </td>
                  <td className="p-4">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={coupon.active} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[--color-secondary] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[--color-primary]"></div>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create/Edit Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-2xl">
            <div className="border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új kupon</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div>
                <label className="block mb-2 font-medium">Kuponkód (nagybetűs)</label>
                <input
                  type="text"
                  placeholder="NYAR2026"
                  className="w-full px-4 py-2 border border-[--color-border] rounded-md uppercase"
                  style={{ fontFamily: 'var(--font-mono)' }}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Típus</label>
                  <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                    <option>Százalék (%)</option>
                    <option>Fix összeg (Ft)</option>
                  </select>
                </div>
                <div>
                  <label className="block mb-2 font-medium">Érték</label>
                  <input type="number" placeholder="10" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Min. rendelési összeg (Ft)</label>
                  <input type="number" placeholder="0" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Max. felhasználás (0 = korlátlan)</label>
                  <input type="number" placeholder="0" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Kategória szűrő</label>
                <select multiple className="w-full px-4 py-2 border border-[--color-border] rounded-md h-24">
                  <option>Minden</option>
                  <option>Kávé</option>
                  <option>Eszköz</option>
                  <option>Merch</option>
                  <option>Csomagok</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <input type="checkbox" id="firstOrder" className="w-4 h-4" />
                <label htmlFor="firstOrder" className="font-medium">
                  Csak első vásárlásra
                </label>
              </div>

              <div>
                <label className="block mb-2 font-medium">Lejárat</label>
                <input type="date" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div className="flex items-center gap-2">
                <input type="checkbox" id="active" className="w-4 h-4" defaultChecked />
                <label htmlFor="active" className="font-medium">
                  Aktív
                </label>
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
