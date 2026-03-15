import { useState } from 'react';
import { Search, Plus, Edit2, Trash2, X } from 'lucide-react';
import { Button } from '../../components/Button';

interface Product {
  id: string;
  thumbnail: string;
  name: string;
  category: string;
  basePrice: number;
  stock: number;
  status: 'active' | 'inactive';
}

export default function AdminProducts() {
  const [isEditing, setIsEditing] = useState(false);
  const [activeTab, setActiveTab] = useState<'basic' | 'coffee' | 'variants' | 'seo' | 'crosssell'>('basic');
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Mock data
  const products: Product[] = [
    {
      id: '1',
      thumbnail: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=80&h=80&fit=crop',
      name: 'Ethiopia Yirgacheffe',
      category: 'Kávé',
      basePrice: 2490,
      stock: 45,
      status: 'active',
    },
    {
      id: '2',
      thumbnail: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=80&h=80&fit=crop',
      name: 'Colombia Huila',
      category: 'Kávé',
      basePrice: 2790,
      stock: 32,
      status: 'active',
    },
    {
      id: '3',
      thumbnail: 'https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?w=80&h=80&fit=crop',
      name: 'Hario V60 Glass',
      category: 'Eszköz',
      basePrice: 4990,
      stock: 12,
      status: 'active',
    },
  ];

  const handleEdit = (product: Product) => {
    setEditingProduct(product);
    setIsEditing(true);
  };

  return (
    <div className="min-h-screen bg-[--color-background] p-6">
      <div className="max-w-[1280px] mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1>Termékek</h1>
          <Button onClick={() => setIsEditing(true)}>
            <Plus className="w-5 h-5 mr-2" />
            Új termék
          </Button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg p-4 mb-6 flex gap-4">
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden kategória</option>
            <option>Kávé</option>
            <option>Eszköz</option>
            <option>Merch</option>
          </select>
          <select className="px-4 py-2 border border-[--color-border] rounded-md">
            <option>Minden státusz</option>
            <option>Aktív</option>
            <option>Inaktív</option>
          </select>
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[--color-muted]" />
            <input
              type="text"
              placeholder="Termék keresése..."
              className="w-full pl-10 pr-4 py-2 border border-[--color-border] rounded-md"
            />
          </div>
        </div>

        {/* DataTable */}
        <div className="bg-white rounded-lg overflow-hidden shadow-sm">
          <table className="w-full">
            <thead className="bg-[--color-background] border-b border-[--color-border]">
              <tr>
                <th className="text-left p-4 font-semibold">Kép</th>
                <th className="text-left p-4 font-semibold">Név</th>
                <th className="text-left p-4 font-semibold">Kategória</th>
                <th className="text-left p-4 font-semibold">Alapár</th>
                <th className="text-left p-4 font-semibold">Készlet</th>
                <th className="text-left p-4 font-semibold">Státusz</th>
                <th className="text-left p-4 font-semibold">Műveletek</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-b border-[--color-border] hover:bg-[--color-background]">
                  <td className="p-4">
                    <img src={product.thumbnail} alt="" className="w-10 h-10 rounded object-cover" />
                  </td>
                  <td className="p-4 font-medium">{product.name}</td>
                  <td className="p-4 text-[--color-muted]">{product.category}</td>
                  <td className="p-4">{product.basePrice.toLocaleString('hu-HU')} Ft</td>
                  <td className="p-4">{product.stock} db</td>
                  <td className="p-4">
                    <span
                      className={`inline-block px-3 py-1 rounded text-xs font-medium ${
                        product.status === 'active'
                          ? 'bg-[--color-success] text-white'
                          : 'bg-[--color-muted] text-white'
                      }`}
                    >
                      {product.status === 'active' ? 'Aktív' : 'Inaktív'}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleEdit(product)}
                        className="p-2 hover:bg-[--color-background] rounded"
                      >
                        <Edit2 className="w-4 h-4 text-[--color-secondary]" />
                      </button>
                      <button className="p-2 hover:bg-[--color-background] rounded">
                        <Trash2 className="w-4 h-4 text-[--color-error]" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Product Editor Modal */}
      {isEditing && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl max-h-[90vh] overflow-auto">
            <div className="sticky top-0 bg-white border-b border-[--color-border] p-6 flex items-center justify-between">
              <h2>{editingProduct ? 'Termék szerkesztése' : 'Új termék'}</h2>
              <button onClick={() => setIsEditing(false)}>
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Tabs */}
            <div className="border-b border-[--color-border] px-6">
              <div className="flex gap-6">
                {[
                  { id: 'basic', label: 'Alap' },
                  { id: 'coffee', label: 'Kávé' },
                  { id: 'variants', label: 'Variánsok' },
                  { id: 'seo', label: 'SEO' },
                  { id: 'crosssell', label: 'Keresztértékesítés' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`py-3 border-b-2 transition-colors ${
                      activeTab === tab.id
                        ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                        : 'border-transparent text-[--color-muted] hover:text-[--color-text]'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="p-6">
              {/* Basic Tab */}
              {activeTab === 'basic' && (
                <div className="space-y-6">
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

                  <div>
                    <label className="block mb-2 font-medium">Leírás (HU)</label>
                    <textarea rows={4} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Leírás (EN)</label>
                    <textarea rows={4} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block mb-2 font-medium">Kategória</label>
                      <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                        <option>Kávé</option>
                        <option>Eszköz</option>
                        <option>Merch</option>
                      </select>
                    </div>
                    <div>
                      <label className="block mb-2 font-medium">Alapár (HUF)</label>
                      <input
                        type="number"
                        className="w-full px-4 py-2 border border-[--color-border] rounded-md"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Kép URL-ek (egy sorban egy URL)</label>
                    <textarea rows={3} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>

                  <div className="flex items-center gap-2">
                    <input type="checkbox" id="active" className="w-4 h-4" />
                    <label htmlFor="active" className="font-medium">
                      Aktív
                    </label>
                  </div>
                </div>
              )}

              {/* Coffee Tab */}
              {activeTab === 'coffee' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block mb-2 font-medium">Origin</label>
                      <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                        <option>Etiópia</option>
                        <option>Kolumbia</option>
                        <option>Kenya</option>
                        <option>Brazília</option>
                      </select>
                    </div>
                    <div>
                      <label className="block mb-2 font-medium">Pörkölés</label>
                      <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                        <option>Világos</option>
                        <option>Közepes</option>
                        <option>Sötét</option>
                      </select>
                    </div>
                    <div>
                      <label className="block mb-2 font-medium">Feldolgozás</label>
                      <select className="w-full px-4 py-2 border border-[--color-border] rounded-md">
                        <option>Mosott</option>
                        <option>Natúr</option>
                        <option>Honey</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Ízvilág címkék (vesszővel elválasztva)</label>
                    <input
                      type="text"
                      placeholder="Citrusos, Virágos, Csokoládés"
                      className="w-full px-4 py-2 border border-[--color-border] rounded-md"
                    />
                  </div>
                </div>
              )}

              {/* Variants Tab */}
              {activeTab === 'variants' && (
                <div>
                  <div className="mb-4 flex justify-between items-center">
                    <h3>Variánsok</h3>
                    <Button variant="outlined">+ Új variáns</Button>
                  </div>
                  <table className="w-full border border-[--color-border] rounded-lg">
                    <thead className="bg-[--color-background]">
                      <tr>
                        <th className="text-left p-3 font-semibold">Opciók</th>
                        <th className="text-left p-3 font-semibold">Ár módosító</th>
                        <th className="text-left p-3 font-semibold">Készlet</th>
                        <th className="text-left p-3 font-semibold">Aktív</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-t border-[--color-border]">
                        <td className="p-3">Szemes, 250g</td>
                        <td className="p-3">0 Ft</td>
                        <td className="p-3">45</td>
                        <td className="p-3">
                          <input type="checkbox" defaultChecked className="w-4 h-4" />
                        </td>
                      </tr>
                      <tr className="border-t border-[--color-border]">
                        <td className="p-3">Szemes, 500g</td>
                        <td className="p-3">+1000 Ft</td>
                        <td className="p-3">32</td>
                        <td className="p-3">
                          <input type="checkbox" defaultChecked className="w-4 h-4" />
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* SEO Tab */}
              {activeTab === 'seo' && (
                <div className="space-y-6">
                  <div>
                    <label className="block mb-2 font-medium">Slug (auto-generált)</label>
                    <input
                      type="text"
                      value="ethiopia-yirgacheffe"
                      readOnly
                      className="w-full px-4 py-2 border border-[--color-border] rounded-md bg-[--color-background]"
                    />
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Meta cím (HU)</label>
                    <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Meta leírás (HU)</label>
                    <textarea rows={3} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                    <p className="text-sm text-[--color-muted] mt-1">0 / 160 karakter</p>
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Meta cím (EN)</label>
                    <input type="text" className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                  </div>

                  <div>
                    <label className="block mb-2 font-medium">Meta leírás (EN)</label>
                    <textarea rows={3} className="w-full px-4 py-2 border border-[--color-border] rounded-md" />
                    <p className="text-sm text-[--color-muted] mt-1">0 / 160 karakter</p>
                  </div>
                </div>
              )}

              {/* Cross-sell Tab */}
              {activeTab === 'crosssell' && (
                <div>
                  <label className="block mb-2 font-medium">Ajánlott termékek (max 3)</label>
                  <p className="text-sm text-[--color-muted] mb-4">
                    Ezek a termékek jelennek meg az "Ezek is érdekelhetnek" szekcióban
                  </p>
                  <select multiple className="w-full px-4 py-2 border border-[--color-border] rounded-md h-40">
                    <option>Colombia Huila</option>
                    <option>Kenya AA</option>
                    <option>Brazil Santos</option>
                    <option>Hario V60 Glass</option>
                  </select>
                </div>
              )}
            </div>

            <div className="sticky bottom-0 bg-white border-t border-[--color-border] p-6 flex justify-end gap-3">
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
