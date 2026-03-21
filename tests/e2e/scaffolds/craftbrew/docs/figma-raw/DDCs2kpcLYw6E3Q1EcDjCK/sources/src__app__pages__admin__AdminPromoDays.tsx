import { useState } from 'react';
import { Plus, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface PromoDay {
  id: string;
  name: string;
  date: string;
  discount: number;
  emailSent: boolean;
  active: boolean;
}

export default function AdminPromoDays() {
  const [isEditing, setIsEditing] = useState(false);

  const promoDays: PromoDay[] = [
    {
      id: '1',
      name: 'Bolt születésnap',
      date: '2026-03-15',
      discount: 20,
      emailSent: true,
      active: true,
    },
    {
      id: '2',
      name: 'Kávé Világnapja',
      date: '2026-10-01',
      discount: 15,
      emailSent: false,
      active: true,
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Promóciós napok</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új promóciós nap
          </Button>
        </div>

        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Név</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Kedvezmény</th>
                <th className="text-left p-4 font-semibold">Email elküldve</th>
                <th className="text-left p-4 font-semibold">Aktív</th>
              </tr>
            </thead>
            <tbody>
              {promoDays.map((promo) => (
                <tr key={promo.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{promo.name}</td>
                  <td className="p-4">{promo.date}</td>
                  <td className="p-4 font-semibold text-[--color-secondary]">{promo.discount}%</td>
                  <td className="p-4">
                    {promo.emailSent ? (
                      <span className="text-[--color-success]">✓ Igen</span>
                    ) : (
                      <span className="text-[--color-muted]">Nem</span>
                    )}
                  </td>
                  <td className="p-4">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={promo.active} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[--color-secondary] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[--color-primary]"></div>
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-2xl">
            <div className="border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új promóciós nap</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Név (HU)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Név (EN)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Dátum</label>
                  <input type="date" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Kedvezmény (%)</label>
                  <input type="number" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Banner szöveg (HU)</label>
                <textarea rows={3} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                <p className="text-sm text-[--color-muted] mt-1">0 / 200 karakter</p>
              </div>

              <div>
                <label className="block mb-2 font-medium">Banner szöveg (EN)</label>
                <textarea rows={3} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                <p className="text-sm text-[--color-muted] mt-1">0 / 200 karakter</p>
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
