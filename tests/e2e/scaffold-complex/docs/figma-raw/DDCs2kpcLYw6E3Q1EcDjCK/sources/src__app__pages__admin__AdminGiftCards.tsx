import { useState } from 'react';

interface GiftCard {
  id: string;
  code: string;
  originalAmount: number;
  balance: number;
  buyer: string;
  expiry: string;
  status: 'active' | 'expired' | 'depleted';
}

export default function AdminGiftCards() {
  const [activeFilter, setActiveFilter] = useState<'all' | 'balance' | 'depleted' | 'expired'>('all');

  const giftCards: GiftCard[] = [
    {
      id: '1',
      code: 'GC-A4F2-9B8E',
      originalAmount: 10000,
      balance: 7500,
      buyer: 'Kovács András',
      expiry: '2027-03-15',
      status: 'active',
    },
    {
      id: '2',
      code: 'GC-C7D1-3A5F',
      originalAmount: 5000,
      balance: 0,
      buyer: 'Nagy Petra',
      expiry: '2027-01-20',
      status: 'depleted',
    },
    {
      id: '3',
      code: 'GC-B9E6-2F4C',
      originalAmount: 20000,
      balance: 0,
      buyer: 'Szabó Eszter',
      expiry: '2025-12-31',
      status: 'expired',
    },
  ];

  const statusConfig = {
    active: { label: 'Aktív', color: '#16A34A' },
    depleted: { label: 'Felhasználva', color: '#78716C' },
    expired: { label: 'Lejárt', color: '#DC2626' },
  };

  const filteredCards = giftCards.filter((card) => {
    if (activeFilter === 'balance') return card.balance > 0;
    if (activeFilter === 'depleted') return card.balance === 0 && card.status === 'depleted';
    if (activeFilter === 'expired') return card.status === 'expired';
    return true;
  });

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Ajándékkártyák</h1>

        {/* Tab Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'all'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Összes
          </button>
          <button
            onClick={() => setActiveFilter('balance')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'balance'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Aktív egyenleggel
          </button>
          <button
            onClick={() => setActiveFilter('depleted')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'depleted'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Felhasználva
          </button>
          <button
            onClick={() => setActiveFilter('expired')}
            className={`px-4 py-2 rounded-md font-medium transition-colors ${
              activeFilter === 'expired'
                ? 'bg-[--color-primary] text-white'
                : 'text-[--color-muted] hover:bg-[--color-background]'
            }`}
          >
            Lejárt
          </button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kód</th>
                <th className="text-left p-4 font-semibold">Eredeti összeg</th>
                <th className="text-left p-4 font-semibold">Egyenleg</th>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Lejárat</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
              </tr>
            </thead>
            <tbody>
              {filteredCards.map((card) => (
                <tr key={card.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4" style={{ fontFamily: 'var(--font-mono)' }}>
                    {card.code}
                  </td>
                  <td className="p-4">{card.originalAmount.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4 font-semibold">
                    {card.balance > 0 ? (
                      <span className="text-[--color-success]">{card.balance.toLocaleString('hu-HU')} Ft</span>
                    ) : (
                      <span className="text-[--color-muted]">0 Ft</span>
                    )}
                  </td>
                  <td className="p-4">{card.buyer}</td>
                  <td className="p-4 text-[--color-muted]">{card.expiry}</td>
                  <td className="p-4">
                    <span
                      className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                      style={{ backgroundColor: statusConfig[card.status].color }}
                    >
                      {statusConfig[card.status].label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
