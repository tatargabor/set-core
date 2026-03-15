import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '../../components/Button';

interface Review {
  id: string;
  stars: number;
  product: string;
  user: string;
  title: string;
  text: string;
  status: 'new' | 'approved' | 'rejected';
  date: string;
}

export default function AdminReviews() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const reviews: Review[] = [
    {
      id: '1',
      stars: 5,
      product: 'Ethiopia Yirgacheffe',
      user: 'Nagy Petra',
      title: 'Fantasztikus minőség!',
      text: 'Az Ethiopia Yirgacheffe a kedvencem, olyan virágos és citrusos ízvilága van. Minden reggel ezzel kezdem a napot.',
      status: 'new',
      date: '2026-03-14',
    },
    {
      id: '2',
      stars: 5,
      product: 'Colombia Huila',
      user: 'Kovács András',
      title: 'Kiváló csomagolás',
      text: 'A szállítás mindig pontos, a csomagolás gyönyörű. Ajándékba is gyakran veszem.',
      status: 'approved',
      date: '2026-03-12',
    },
  ];

  const statusConfig = {
    new: { label: 'Új', color: '#3B82F6' },
    approved: { label: 'Elfogadva', color: '#16A34A' },
    rejected: { label: 'Elutasítva', color: '#DC2626' },
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <h1 className="mb-8">Értékelések</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Új</option>
            <option>Elfogadva</option>
            <option>Elutasítva</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Min. csillag</option>
            <option>5 csillag</option>
            <option>4+ csillag</option>
            <option>3+ csillag</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md flex-1">
            <option>Minden termék</option>
            <option>Ethiopia Yirgacheffe</option>
            <option>Colombia Huila</option>
          </select>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold w-24">★</th>
                <th className="text-left p-4 font-semibold">Termék</th>
                <th className="text-left p-4 font-semibold">Felhasználó</th>
                <th className="text-left p-4 font-semibold">Cím</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold w-20"></th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                <>
                  <tr
                    key={review.id}
                    className="border-b border-[--color-border] hover:bg-[--color-background] cursor-pointer"
                    onClick={() => setExpandedId(expandedId === review.id ? null : review.id)}
                  >
                    <td className="p-4">
                      <div className="flex gap-1">
                        {[...Array(review.stars)].map((_, i) => (
                          <span key={i} className="text-[--color-secondary]">
                            ★
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="p-4 font-medium">{review.product}</td>
                    <td className="p-4">{review.user}</td>
                    <td className="p-4 text-[--color-muted] truncate max-w-xs">{review.title}</td>
                    <td className="p-4">
                      <span
                        className="inline-block px-3 py-1 rounded text-xs font-medium text-white"
                        style={{ backgroundColor: statusConfig[review.status].color }}
                      >
                        {statusConfig[review.status].label}
                      </span>
                    </td>
                    <td className="p-4 text-[--color-muted]">{review.date}</td>
                    <td className="p-4">
                      {expandedId === review.id ? (
                        <ChevronUp className="w-5 h-5 text-[--color-muted]" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-[--color-muted]" />
                      )}
                    </td>
                  </tr>
                  {expandedId === review.id && (
                    <tr>
                      <td colSpan={7} className="bg-[--color-background] p-6">
                        <div className="max-w-3xl space-y-6">
                          {/* Review Content */}
                          <div>
                            <div className="flex gap-1 mb-2">
                              {[...Array(review.stars)].map((_, i) => (
                                <span key={i} className="text-[--color-secondary] text-xl">
                                  ★
                                </span>
                              ))}
                            </div>
                            <h3 className="mb-2">{review.title}</h3>
                            <p className="text-[--color-text] mb-4">{review.text}</p>
                            <div className="flex items-center gap-4 text-sm text-[--color-muted]">
                              <span>
                                <strong>Felhasználó:</strong> {review.user}
                              </span>
                              <span>
                                <strong>Termék:</strong>{' '}
                                <a href="#" className="text-[--color-secondary] hover:underline">
                                  {review.product}
                                </a>
                              </span>
                            </div>
                          </div>

                          {/* Action Buttons */}
                          {review.status === 'new' && (
                            <div className="flex gap-3">
                              <Button variant="primary">Elfogadás</Button>
                              <button className="px-6 py-3 bg-[--color-error] text-white rounded-md font-medium hover:opacity-90">
                                Elutasítás
                              </button>
                            </div>
                          )}

                          {/* Reply Section */}
                          <div className="border-t border-[--color-border] pt-6">
                            <label className="block mb-2 font-medium">CraftBrew válasza</label>
                            <textarea
                              rows={4}
                              placeholder="Válasz írása..."
                              className="w-full px-4 py-2 border border-[--color-border] rounded-md mb-2"
                            />
                            <p className="text-sm text-[--color-muted] mb-3">0 / 500 karakter</p>
                            <Button variant="outlined">Válasz küldése</Button>
                          </div>

                          {/* Example Reply Display */}
                          {review.status === 'approved' && (
                            <div className="bg-white p-4 rounded-lg border-l-4 border-[--color-secondary]">
                              <p className="font-medium text-[--color-primary] mb-2">CraftBrew válaszolt:</p>
                              <p className="text-[--color-text]">
                                Köszönjük a kedves értékelést, Petra! Nagyon örülünk, hogy tetszik az Ethiopia
                                Yirgacheffe. 🙂
                              </p>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
