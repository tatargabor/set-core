import { useState } from 'react';
import { Plus, X, Edit2 } from 'lucide-react';
import { Button } from '../../components/Button';

interface Story {
  id: string;
  title: string;
  category: string;
  status: 'draft' | 'published';
  date: string;
}

export default function AdminStories() {
  const [isEditing, setIsEditing] = useState(false);
  const [contentLang, setContentLang] = useState<'hu' | 'en'>('hu');

  const stories: Story[] = [
    {
      id: '1',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      status: 'published',
      date: '2026-03-10',
    },
    {
      id: '2',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      status: 'draft',
      date: '2026-03-08',
    },
  ];

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Sztorik</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új sztori
          </Button>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Cím</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Dátum</th>
                <th className="text-left p-4 font-semibold">Szerkesztés</th>
              </tr>
            </thead>
            <tbody>
              {stories.map((story) => (
                <tr key={story.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4 font-medium">{story.title}</td>
                  <td className="p-4">{story.category}</td>
                  <td className="p-4">
                    <span
                      className={`inline-block px-3 py-1 rounded text-xs font-medium text-white ${
                        story.status === 'published' ? 'bg-[--color-success]' : 'bg-[--color-muted]'
                      }`}
                    >
                      {story.status === 'published' ? 'Publikált' : 'Vázlat'}
                    </span>
                  </td>
                  <td className="p-4 text-[--color-muted]">{story.date}</td>
                  <td className="p-4">
                    <button onClick={() => setIsEditing(true)} className="p-2 hover:bg-[--color-background] rounded">
                      <Edit2 className="w-4 h-4 text-[--color-secondary]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Story Editor Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>Új sztori</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Language Tabs */}
              <div className="flex gap-4 border-b border-[--color-border]">
                <button
                  onClick={() => setContentLang('hu')}
                  className={`pb-2 px-4 border-b-2 transition-colors ${
                    contentLang === 'hu'
                      ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                      : 'border-transparent text-[--color-muted]'
                  }`}
                >
                  Magyar
                </button>
                <button
                  onClick={() => setContentLang('en')}
                  className={`pb-2 px-4 border-b-2 transition-colors ${
                    contentLang === 'en'
                      ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                      : 'border-transparent text-[--color-muted]'
                  }`}
                >
                  English
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Cím (HU)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Cím (EN)</label>
                  <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Kategória</label>
                  <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                    <option>Eredet</option>
                    <option>Főzés</option>
                    <option>Egészség</option>
                    <option>Fenntarthatóság</option>
                  </select>
                </div>
                <div>
                  <label className="block mb-2 font-medium">Slug (auto)</label>
                  <input
                    type="text"
                    value="yirgacheffe-origin"
                    readOnly
                    className="w-full px-4 py-2 border border-[--color-border] rounded-md bg-[--color-background]"
                  />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Tartalom (HU)</label>
                <textarea rows={10} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div>
                <label className="block mb-2 font-medium">Tartalom (EN)</label>
                <textarea rows={10} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div>
                <label className="block mb-2 font-medium">Cover kép URL</label>
                <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block mb-2 font-medium">Szerző</label>
                  <input type="text" placeholder="CraftBrew Team" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
                <div>
                  <label className="block mb-2 font-medium">Publikálás dátuma</label>
                  <input type="date" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                </div>
              </div>

              <div>
                <label className="block mb-2 font-medium">Kapcsolódó termékek (max 4)</label>
                <select multiple className="w-full px-4 py-2 border border-[--color-border] rounded-md h-24">
                  <option>Ethiopia Yirgacheffe</option>
                  <option>Colombia Huila</option>
                  <option>Kenya AA</option>
                  <option>Hario V60 Glass</option>
                </select>
              </div>

              <div>
                <label className="block mb-2 font-medium">Státusz</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2">
                    <input type="radio" name="status" value="draft" className="w-4 h-4" />
                    <span>Vázlat</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input type="radio" name="status" value="published" className="w-4 h-4" />
                    <span>Publikált</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white border-t border-[--color-border] p-6 flex justify-end gap-3">
              <Button variant="outlined">Előnézet</Button>
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
