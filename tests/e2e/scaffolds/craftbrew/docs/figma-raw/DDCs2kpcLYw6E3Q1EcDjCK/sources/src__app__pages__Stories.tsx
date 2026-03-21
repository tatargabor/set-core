import { Link } from 'react-router';
import { useState } from 'react';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';

export default function Stories() {
  const [activeCategory, setActiveCategory] = useState('Mind');
  const categories = ['Mind', 'Eredet', 'Pörkölés', 'Főzés', 'Egészség', 'Ajándék'];

  const stories = [
    {
      id: 'yirgacheffe-origin',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=600',
      date: '2026-03-10',
      excerpt: 'Fedezd fel az etióp Yirgacheffe régió egyedi kávékultúráját és történetét...',
    },
    {
      id: 'brewing-guide',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=600',
      date: '2026-03-08',
      excerpt: 'Lépésről lépésre guide a tökéletes pour over kávé elkészítéséhez...',
    },
    {
      id: 'coffee-health',
      title: 'A kávé egészségügyi előnyei',
      category: 'Egészség',
      image: 'https://images.unsplash.com/photo-1713742000733-f038b0bf61cd?w=600',
      date: '2026-03-05',
      excerpt: 'Tudományos kutatások a kávé pozitív hatásairól a szervezetre...',
    },
    {
      id: 'roasting-process',
      title: 'A pörkölés művészete',
      category: 'Pörkölés',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=600',
      date: '2026-03-01',
      excerpt: 'Betekintés a specialty kávé pörkölésének rejtelmeibe...',
    },
    {
      id: 'gift-guide',
      title: 'Kávé ajándékozási útmutató',
      category: 'Ajándék',
      image: 'https://images.unsplash.com/photo-1772200514909-c0ba6cba34f0?w=600',
      date: '2026-02-28',
      excerpt: 'Tippek és ötletek kávékedvelőknek szóló ajándékokhoz...',
    },
    {
      id: 'colombia-farms',
      title: 'Kolumbiai kávéültetvények',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?w=600',
      date: '2026-02-25',
      excerpt: 'Látogatás a kolumbiai Huila régió kávéfarmjain...',
    },
  ];

  const filteredStories = activeCategory === 'Mind' 
    ? stories 
    : stories.filter(story => story.category === activeCategory);

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      <h1 className="mb-8">Sztorik</h1>

      {/* Category Tabs */}
      <div className="flex gap-6 mb-8 overflow-x-auto pb-2">
        {categories.map((category) => (
          <button
            key={category}
            onClick={() => setActiveCategory(category)}
            className={`whitespace-nowrap pb-2 border-b-2 transition-colors ${
              activeCategory === category
                ? 'border-[--color-secondary] text-[--color-secondary] font-medium'
                : 'border-transparent text-[--color-muted] hover:text-[--color-text]'
            }`}
          >
            {category}
          </button>
        ))}
      </div>

      {/* Stories Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredStories.map((story) => (
          <Link
            key={story.id}
            to={`/sztorik/${story.id}`}
            className="group bg-white rounded-lg overflow-hidden shadow-md hover:shadow-xl transition-shadow"
          >
            <div className="aspect-video overflow-hidden">
              <ImageWithFallback
                src={story.image}
                alt={story.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              />
            </div>
            <div className="p-6">
              <span className="inline-block px-3 py-1 bg-[--color-secondary] text-white text-xs rounded-full mb-3">
                {story.category}
              </span>
              <h3 className="mb-2">{story.title}</h3>
              <p className="text-sm text-[--color-muted] mb-3">{story.date}</p>
              <p className="text-sm text-[--color-muted]">{story.excerpt}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
