import { useState } from 'react';
import { Search, X, Check } from 'lucide-react';
import { Button } from '../../components/Button';

interface Order {
  id: string;
  number: string;
  customer: string;
  date: string;
  total: number;
  status: 'new' | 'processing' | 'packed' | 'shipping' | 'delivered' | 'cancelled';
}

const statusConfig = {
  new: { label: 'Új', color: '#3B82F6' },
  processing: { label: 'Feldolgozás', color: '#EAB308' },
  packed: { label: 'Csomagolva', color: '#F97316' },
  shipping: { label: 'Szállítás', color: '#A855F7' },
  delivered: { label: 'Kézbesítve', color: '#16A34A' },
  cancelled: { label: 'Lemondva', color: '#DC2626' },
};

export default function AdminOrders() {
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);

  const orders: Order[] = [
    {
      id: '1',
      number: '#1042',
      customer: 'Nagy Petra',
      date: '2026-03-15 10:24',
      total: 7480,
      status: 'processing',
    },
    {
      id: '2',
      number: '#1041',
      customer: 'Kovács András',
      date: '2026-03-15 09:15',
      total: 12490,
      status: 'packed',
    },
    {
      id: '3',
      number: '#1040',
      customer: 'Szabó Eszter',
      date: '2026-03-14 16:42',
      total: 3490,
      status: 'delivered',
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Rendelések</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Új</option>
            <option>Feldolgozás</option>
            <option>Kézbesítve</option>
          </select>
          <input
            type="date"
            className="px-4 py-2 border border-[--color-border] rounded-md"
            placeholder="Dátum-tól"
          />
          <input
            type="date"
            className="px-4 py-2 border border-[--color-border] rounded-md"
            placeholder="Dátum-ig"
          />
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
            <input
              type="text"
              placeholder="Rendelésszám vagy vásárló neve..."
              className="w-full pl-10 pr-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Szám</th>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Összeg</th>
                <th className="text-left p-4 font-semibold">Állapot</th>
                <th className="text-left p-4 font-semibold">Részletek</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr key={order.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4" style={{ fontFamily: 'var(--font-mono)' }}>
                    {order.number}
                  </td>
                  <td className="p-4 font-medium">{order.customer}</td>
                  <td className="p-4 text-[--color-muted]">{order.date}</td>
                  <td className="p-4 font-semibold">{order.total.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4">
                    <span
                      className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                      style={{ backgroundColor: statusConfig[order.status].color }}
                    >
                      {statusConfig[order.status].label}
                    </span>
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => setSelectedOrder(order)}
                      className="text-[--color-secondary] hover:underline font-medium"
                    >
                      Megtekintés
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Order Detail Slide-in Panel */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/50 z-50 flex justify-end">
          <div className="bg-white w-full max-w-2xl h-full overflow-auto">
            <div className="sticky top-0 bg-white border-b border-[--color-border] p-6 flex items-center justify-between">
              <div>
                <h2 style={{ fontFamily: 'var(--font-mono)' }}>{selectedOrder.number}</h2>
                <p className="text-[--color-muted]">{selectedOrder.date}</p>
              </div>
              <button onClick={() => setSelectedOrder(null)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Customer Info */}
              <div>
                <h3 className="mb-3">Vásárló</h3>
                <div className="bg-[--color-background] p-4 rounded-lg">
                  <p className="font-medium">{selectedOrder.customer}</p>
                  <p className="text-sm text-[--color-muted]">nagy.petra@email.com</p>
                  <p className="text-sm text-[--color-muted] mt-2">
                    1075 Budapest, Kazinczy u. 28.
                    <br />
                    +36 30 123 4567
                  </p>
                </div>
              </div>

              {/* Line Items */}
              <div>
                <h3 className="mb-3">Termékek</h3>
                <div className="space-y-3">
                  <div className="flex gap-4 bg-[--color-background] p-4 rounded-lg">
                    <img
                      src="https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=80&h=80&fit=crop"
                      alt=""
                      className="w-16 h-16 rounded object-cover"
                    />
                    <div className="flex-1">
                      <p className="font-medium">Ethiopia Yirgacheffe</p>
                      <p className="text-sm text-[--color-muted]">Szemes, 500g</p>
                      <p className="text-sm text-[--color-muted]">2 × 2 490 Ft</p>
                    </div>
                    <p className="font-semibold">4 980 Ft</p>
                  </div>
                  <div className="flex gap-4 bg-[--color-background] p-4 rounded-lg">
                    <img
                      src="https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=80&h=80&fit=crop"
                      alt=""
                      className="w-16 h-16 rounded object-cover"
                    />
                    <div className="flex-1">
                      <p className="font-medium">Hario V60 Glass</p>
                      <p className="text-sm text-[--color-muted]">-</p>
                      <p className="text-sm text-[--color-muted]">1 × 4 990 Ft</p>
                    </div>
                    <p className="font-semibold">4 990 Ft</p>
                  </div>
                </div>
              </div>

              {/* Price Breakdown */}
              <div className="border-t border-[--color-border] pt-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-[--color-muted]">Részösszeg</span>
                    <span>9 970 Ft</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[--color-muted]">Kedvezmény (ELSO10)</span>
                    <span className="text-[--color-success]">-997 Ft</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[--color-muted]">Szállítás</span>
                    <span>990 Ft</span>
                  </div>
                  <div className="flex justify-between text-lg font-bold border-t border-[--color-border] pt-2 mt-2">
                    <span>Összesen</span>
                    <span className="text-[--color-primary]">{selectedOrder.total.toLocaleString('hu-HU')} Ft</span>
                  </div>
                </div>
              </div>

              {/* Stripe Payment ID */}
              <div className="bg-[--color-background] p-4 rounded-lg">
                <p className="text-sm text-[--color-muted] mb-1">Stripe Payment ID</p>
                <p style={{ fontFamily: 'var(--font-mono)' }} className="text-sm">
                  pi_3MtwBwLkdIwHu7ix28a3tqPa
                </p>
              </div>

              {/* Status Flow Buttons */}
              <div>
                <h3 className="mb-3">Állapot módosítása</h3>
                <div className="flex gap-2 flex-wrap">
                  <Button variant="outlined" className="text-sm">
                    Feldolgozás
                  </Button>
                  <Button variant="outlined" className="text-sm">
                    Csomagolva
                  </Button>
                  <Button variant="outlined" className="text-sm">
                    Szállítás
                  </Button>
                  <Button variant="primary" className="text-sm">
                    <Check className="w-4 h-4 mr-1" />
                    Kézbesítve
                  </Button>
                </div>
              </div>

              {/* Status Timeline */}
              <div>
                <h3 className="mb-3">Állapot történet</h3>
                <div className="space-y-4">
                  <div className="flex gap-3">
                    <div className="w-2 h-2 rounded-full bg-[--color-success] mt-2"></div>
                    <div className="flex-1">
                      <p className="font-medium">Feldolgozás</p>
                      <p className="text-sm text-[--color-muted]">2026-03-15 11:30</p>
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <div className="w-2 h-2 rounded-full bg-[--color-success] mt-2"></div>
                    <div className="flex-1">
                      <p className="font-medium">Új rendelés</p>
                      <p className="text-sm text-[--color-muted]">2026-03-15 10:24</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Cancel Button */}
              <div className="border-t border-[--color-border] pt-4">
                <button className="w-full py-3 bg-[--color-error] text-white rounded-md font-medium hover:opacity-90">
                  Rendelés lemondása
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
