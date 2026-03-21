import { useState } from 'react';
import { Calendar, Check } from 'lucide-react';
import { Button } from '../../components/Button';

interface Delivery {
  id: string;
  time: string;
  customer: string;
  address: string;
  product: string;
  delivered: boolean;
}

export default function AdminDeliveries() {
  const [selectedDate, setSelectedDate] = useState('2026-03-15');
  const [deliveries, setDeliveries] = useState<Delivery[]>([
    {
      id: '1',
      time: '7:30',
      customer: 'Nagy Petra',
      address: '1075 Budapest, Kazinczy u. 28.',
      product: 'Ethiopia Yirgacheffe — Szemes, 500g',
      delivered: true,
    },
    {
      id: '2',
      time: '8:15',
      customer: 'Kovács András',
      address: '1061 Budapest, Andrássy út 45.',
      product: 'Colombia Huila — Őrölt, 250g',
      delivered: false,
    },
    {
      id: '3',
      time: '8:45',
      customer: 'Szabó Eszter',
      address: '1073 Budapest, Erzsébet krt. 12.',
      product: 'Kenya AA — Szemes, 500g',
      delivered: true,
    },
  ]);

  const morningDeliveries = deliveries.filter((d) => d.time >= '6:00' && d.time < '9:00');
  const forenoonDeliveries = deliveries.filter((d) => d.time >= '9:00' && d.time < '12:00');
  const afternoonDeliveries = deliveries.filter((d) => d.time >= '14:00' && d.time < '17:00');

  const toggleDelivered = (id: string) => {
    setDeliveries((prev) =>
      prev.map((d) => (d.id === id ? { ...d, delivered: !d.delivered } : d))
    );
  };

  const markAllDelivered = () => {
    setDeliveries((prev) => prev.map((d) => ({ ...d, delivered: true })));
  };

  const totalDeliveries = deliveries.length;
  const subscriptionCount = 7; // mock
  const singleOrderCount = 3; // mock
  const budapestCount = 8; // mock
  const outsideCount = 2; // mock

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Szállítás</h1>
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-[--color-muted]" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="px-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* Summary Bar */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-6 text-sm">
          <div>
            <span className="text-[--color-muted]">Összesen:</span>{' '}
            <span className="font-semibold">{totalDeliveries}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Előfizetés:</span>{' '}
            <span className="font-semibold">{subscriptionCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Egyszeri:</span>{' '}
            <span className="font-semibold">{singleOrderCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">Budapest:</span>{' '}
            <span className="font-semibold">{budapestCount}</span>
          </div>
          <div className="border-l border-[--color-border] pl-6">
            <span className="text-[--color-muted]">+20km:</span>{' '}
            <span className="font-semibold">{outsideCount}</span>
          </div>
          <div className="ml-auto">
            <Button onClick={markAllDelivered}>
              <Check className="w-4 h-4 mr-2" />
              Mind kézbesítve
            </Button>
          </div>
        </div>

        {/* Morning Section */}
        {morningDeliveries.length > 0 && (
          <div className="mb-6">
            <h2 className="mb-4">
              Reggel (6:00-9:00) — {morningDeliveries.length} tétel
            </h2>
            <div className="bg-white rounded-lg overflow-hidden shadow-sm">
              <table className="w-full">
                <thead className="bg-[--color-background] border-b border-[--color-border]">
                  <tr>
                    <th className="text-left p-4 font-semibold w-24">Idő</th>
                    <th className="text-left p-4 font-semibold">Vásárló</th>
                    <th className="text-left p-4 font-semibold">Cím</th>
                    <th className="text-left p-4 font-semibold">Termék + Variáns</th>
                    <th className="text-left p-4 font-semibold w-48">Státusz</th>
                  </tr>
                </thead>
                <tbody>
                  {morningDeliveries.map((delivery) => (
                    <tr key={delivery.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                      <td className="p-4 font-medium">{delivery.time}</td>
                      <td className="p-4">{delivery.customer}</td>
                      <td className="p-4 text-[--color-muted]">{delivery.address}</td>
                      <td className="p-4">{delivery.product}</td>
                      <td className="p-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={delivery.delivered}
                            onChange={() => toggleDelivered(delivery.id)}
                            className="w-4 h-4"
                          />
                          <span className={delivery.delivered ? 'text-[--color-success] font-medium' : ''}>
                            {delivery.delivered ? '✓ Kézbesítve' : 'Kézbesítés alatt'}
                          </span>
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Forenoon Section */}
        {forenoonDeliveries.length > 0 && (
          <div className="mb-6">
            <h2 className="mb-4">
              Délelőtt (9:00-12:00) — {forenoonDeliveries.length} tétel
            </h2>
            <div className="bg-white rounded-lg overflow-hidden shadow-sm">
              <table className="w-full">
                <thead className="bg-[--color-background] border-b border-[--color-border]">
                  <tr>
                    <th className="text-left p-4 font-semibold w-24">Idő</th>
                    <th className="text-left p-4 font-semibold">Vásárló</th>
                    <th className="text-left p-4 font-semibold">Cím</th>
                    <th className="text-left p-4 font-semibold">Termék + Variáns</th>
                    <th className="text-left p-4 font-semibold w-48">Státusz</th>
                  </tr>
                </thead>
                <tbody>
                  {forenoonDeliveries.map((delivery) => (
                    <tr key={delivery.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                      <td className="p-4 font-medium">{delivery.time}</td>
                      <td className="p-4">{delivery.customer}</td>
                      <td className="p-4 text-[--color-muted]">{delivery.address}</td>
                      <td className="p-4">{delivery.product}</td>
                      <td className="p-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={delivery.delivered}
                            onChange={() => toggleDelivered(delivery.id)}
                            className="w-4 h-4"
                          />
                          <span className={delivery.delivered ? 'text-[--color-success] font-medium' : ''}>
                            {delivery.delivered ? '✓ Kézbesítve' : 'Kézbesítés alatt'}
                          </span>
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Afternoon Section */}
        {afternoonDeliveries.length > 0 && (
          <div className="mb-6">
            <h2 className="mb-4">
              Délután (14:00-17:00) — {afternoonDeliveries.length} tétel
            </h2>
            <div className="bg-white rounded-lg overflow-hidden shadow-sm">
              <table className="w-full">
                <thead className="bg-[--color-background] border-b border-[--color-border]">
                  <tr>
                    <th className="text-left p-4 font-semibold w-24">Idő</th>
                    <th className="text-left p-4 font-semibold">Vásárló</th>
                    <th className="text-left p-4 font-semibold">Cím</th>
                    <th className="text-left p-4 font-semibold">Termék + Variáns</th>
                    <th className="text-left p-4 font-semibold w-48">Státusz</th>
                  </tr>
                </thead>
                <tbody>
                  {afternoonDeliveries.map((delivery) => (
                    <tr key={delivery.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                      <td className="p-4 font-medium">{delivery.time}</td>
                      <td className="p-4">{delivery.customer}</td>
                      <td className="p-4 text-[--color-muted]">{delivery.address}</td>
                      <td className="p-4">{delivery.product}</td>
                      <td className="p-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={delivery.delivered}
                            onChange={() => toggleDelivered(delivery.id)}
                            className="w-4 h-4"
                          />
                          <span className={delivery.delivered ? 'text-[--color-success] font-medium' : ''}>
                            {delivery.delivered ? '✓ Kézbesítve' : 'Kézbesítés alatt'}
                          </span>
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
