import { Button } from '../../components/Button';

interface Subscription {
  id: string;
  customer: string;
  coffee: string;
  frequency: string;
  nextDelivery: string;
  status: 'active' | 'paused' | 'cancelled';
}

export default function AdminSubscriptions() {
  const subscriptions: Subscription[] = [
    {
      id: '1',
      customer: 'Nagy Petra',
      coffee: 'Ethiopia Yirgacheffe — Szemes, 500g',
      frequency: 'Naponta',
      nextDelivery: '2026-03-16 (holnap)',
      status: 'active',
    },
    {
      id: '2',
      customer: 'Kovács András',
      coffee: 'Colombia Huila — Őrölt, 250g',
      frequency: 'Hetente',
      nextDelivery: '2026-03-20',
      status: 'paused',
    },
    {
      id: '3',
      customer: 'Szabó Eszter',
      coffee: 'Kenya AA — Szemes, 500g',
      frequency: 'Kéthetente',
      nextDelivery: '—',
      status: 'cancelled',
    },
  ];

  const statusConfig = {
    active: { label: 'Aktív', color: '#16A34A' },
    paused: { label: 'Szüneteltetve', color: '#EAB308' },
    cancelled: { label: 'Lemondva', color: '#DC2626' },
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Előfizetések</h1>

        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Vásárló</th>
                <th className="text-left p-4 font-semibold">Kávé</th>
                <th className="text-left p-4 font-semibold">Gyakoriság</th>
                <th className="text-left p-4 font-semibold">Következő szállítás</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Műveletek</th>
              </tr>
            </thead>
            <tbody>
              {subscriptions.map((sub) => (
                <tr key={sub.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{sub.customer}</td>
                  <td className="p-4">{sub.coffee}</td>
                  <td className="p-4">{sub.frequency}</td>
                  <td className="p-4 text-[--color-muted]">{sub.nextDelivery}</td>
                  <td className="p-4">
                    <span
                      className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                      style={{ backgroundColor: statusConfig[sub.status].color }}
                    >
                      {statusConfig[sub.status].label}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-2">
                      {sub.status === 'active' && (
                        <Button variant="outlined" className="text-sm py-1">
                          Szüneteltetés
                        </Button>
                      )}
                      {sub.status === 'paused' && (
                        <Button variant="outlined" className="text-sm py-1">
                          Aktiválás
                        </Button>
                      )}
                      <Button variant="outlined" className="text-sm py-1">
                        Módosítás
                      </Button>
                      {sub.status !== 'cancelled' && (
                        <button className="px-3 py-1 text-sm bg-[--color-error] text-white rounded-md hover:opacity-90">
                          Lemondás
                        </button>
                      )}
                    </div>
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
