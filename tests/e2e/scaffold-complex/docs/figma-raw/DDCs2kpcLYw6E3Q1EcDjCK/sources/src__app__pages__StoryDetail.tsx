import { Link, useParams } from 'react-router';
import { ChevronRight, Facebook, Share2 } from 'lucide-react';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { ProductCard } from '../components/ProductCard';

export default function StoryDetail() {
  const { slug } = useParams();

  const story = {
    id: slug || 'yirgacheffe-origin',
    title: 'Yirgacheffe: A kávé szülőföldje',
    category: 'Eredet',
    image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?w=1200',
    date: '2026-03-10',
    author: 'CraftBrew csapat',
    content: `
      <p>Az etióp Yirgacheffe régió a világ egyik legkülönlegesebb kávétermő vidéke. A magas tengerszint feletti magasságban, ideális klímában termelt kávé egyedi virágos és citrusos aromáival hódította meg a specialty kávé szerelmeseit világszerte.</p>
      
      <h3>A régió története</h3>
      <p>Yirgacheffe Etiópia délnyugati részén található, ahol a kávé természetes élőhelyén nő. A helyi közösségek generációk óta foglalkoznak kávétermesztéssel, és büszkék egyedi feldolgozási módszereikre.</p>
      
      <h3>Feldolgozás és ízvilág</h3>
      <p>A Yirgacheffe kávét jellemzően mosott (washed) módszerrel dolgozzák fel, ami hozzájárul tiszta, komplex ízprofiljához. A jellegzetes jázmin, bergamott és citrusos jegyek különösen filter kávéban érvényesülnek.</p>
      
      <h3>Miért különleges?</h3>
      <p>A régió egyedi terroir-ja - a talaj, klíma és magasság kombinációja - olyan kávét eredményez, amely egyedülálló a világon. Érdemes kipróbálni pour over vagy V60 módszerrel, hogy teljes mértékben élvezhessük a finomságokat.</p>
    `,
  };

  const relatedProducts = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?w=400',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
    },
    {
      id: 'v60-dripper',
      name: 'Hario V60 Dripper',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?w=400',
      price: 3990,
      rating: 5,
      reviewCount: 24,
    },
  ];

  return (
    <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-[--color-muted] mb-8">
        <Link to="/" className="hover:text-[--color-secondary]">
          Főoldal
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/sztorik" className="hover:text-[--color-secondary]">
          Sztorik
        </Link>
        <ChevronRight className="w-4 h-4" />
        <Link to="/sztorik" className="hover:text-[--color-secondary]">
          {story.category}
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-[--color-text]">{story.title}</span>
      </nav>

      {/* Cover Image */}
      <div className="aspect-video md:aspect-[21/9] overflow-hidden rounded-lg mb-8">
        <ImageWithFallback src={story.image} alt={story.title} className="w-full h-full object-cover" />
      </div>

      {/* Article Header */}
      <div className="max-w-3xl mx-auto mb-8">
        <div className="flex items-center gap-4 mb-4">
          <span className="px-3 py-1 bg-[--color-secondary] text-white text-sm rounded-full">{story.category}</span>
          <span className="text-sm text-[--color-muted]">{story.date}</span>
          <span className="text-sm text-[--color-muted]">{story.author}</span>
        </div>
        <h1 className="mb-6">{story.title}</h1>

        {/* Share Buttons */}
        <div className="flex items-center gap-3 pb-6 border-b border-[--color-border]">
          <span className="text-sm text-[--color-muted]">Megosztás:</span>
          <button className="p-2 rounded-full hover:bg-[--color-background] transition-colors">
            <Facebook className="w-5 h-5 text-[--color-muted]" />
          </button>
          <button className="p-2 rounded-full hover:bg-[--color-background] transition-colors">
            <Share2 className="w-5 h-5 text-[--color-muted]" />
          </button>
        </div>
      </div>

      {/* Article Content */}
      <article className="max-w-3xl mx-auto prose prose-lg mb-16">
        <div
          className="text-[--color-text] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: story.content }}
          style={{ lineHeight: 1.8 }}
        />
      </article>

      {/* Related Products */}
      <div className="max-w-5xl mx-auto">
        <h2 className="mb-8">Kapcsolódó termékek</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {relatedProducts.map((product) => (
            <ProductCard key={product.id} {...product} />
          ))}
        </div>
      </div>
    </div>
  );
}
