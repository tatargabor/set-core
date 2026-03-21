import { Link } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { Button } from '../components/Button';
import { ProductCard } from '../components/ProductCard';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';

export default function Home() {
  // Mock product data
  const featuredCoffees = [
    {
      id: 'ethiopia-yirgacheffe',
      name: 'Ethiopia Yirgacheffe',
      image: 'https://images.unsplash.com/photo-1772391264887-50a9e650e0fd?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxldGhpb3BpYW4lMjBjb2ZmZWUlMjBiZWFuc3xlbnwxfHx8fDE3NzMzNDgxNjN8MA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2490,
      rating: 5,
      reviewCount: 12,
      origin: 'Etiópia',
      roast: 'Világos',
      isNew: true,
    },
    {
      id: 'colombia-huila',
      name: 'Colombia Huila',
      image: 'https://images.unsplash.com/photo-1772141614991-eea2a95e770c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2xvbWJpYSUyMGNvZmZlZSUyMHJvYXN0ZWR8ZW58MXx8fHwxNzczMzQ4MTYzfDA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2790,
      rating: 5,
      reviewCount: 8,
      origin: 'Kolumbia',
      roast: 'Közepes',
    },
    {
      id: 'kenya-aa',
      name: 'Kenya AA',
      image: 'https://images.unsplash.com/photo-1770326965745-079ca2abbc06?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxrZW55YSUyMGNvZmZlZSUyMHNwZWNpYWx0eXxlbnwxfHx8fDE3NzMzNDgxNjN8MA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 3190,
      rating: 5,
      reviewCount: 15,
      origin: 'Kenya',
      roast: 'Világos',
    },
    {
      id: 'brazil-santos',
      name: 'Brazil Santos',
      image: 'https://images.unsplash.com/photo-1708362524830-989c281f5159?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxicmF6aWwlMjBjb2ZmZWUlMjBkYXJrJTIwcm9hc3R8ZW58MXx8fHwxNzczMzQ4MTY0fDA&ixlib=rb-4.1.0&q=80&w=1080',
      price: 2290,
      rating: 4,
      reviewCount: 10,
      origin: 'Brazília',
      roast: 'Sötét',
    },
  ];

  const stories = [
    {
      id: 'yirgacheffe-origin',
      title: 'Yirgacheffe: A kávé szülőföldje',
      category: 'Eredet',
      image: 'https://images.unsplash.com/photo-1625465115622-4a265061db77?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjByb2FzdGluZyUyMHByb2Nlc3N8ZW58MXx8fHwxNzczMjg3OTQyfDA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-10',
    },
    {
      id: 'brewing-guide',
      title: 'Tökéletes főzési útmutató',
      category: 'Főzés',
      image: 'https://images.unsplash.com/photo-1550559256-32644b7a2993?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBicmV3aW5nJTIwcG91ciUyMG92ZXJ8ZW58MXx8fHwxNzczMjg2Njg5fDA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-08',
    },
    {
      id: 'coffee-health',
      title: 'A kávé egészségügyi előnyei',
      category: 'Egészség',
      image: 'https://images.unsplash.com/photo-1713742000733-f038b0bf61cd?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBoZWFsdGglMjBiZW5lZml0c3xlbnwxfHx8fDE3NzMzNDgxNjV8MA&ixlib=rb-4.1.0&q=80&w=1080',
      date: '2026-03-05',
    },
  ];

  const testimonials = [
    {
      id: 1,
      stars: 5,
      quote: 'Fantasztikus minőség! Az Ethiopia Yirgacheffe a kedvencem, olyan virágos és citrusos ízvilága van.',
      name: 'Nagy Petra',
      product: 'Ethiopia Yirgacheffe',
    },
    {
      id: 2,
      stars: 5,
      quote: 'A szállítás mindig pontos, a csomagolás gyönyörű. Ajándékba is gyakran veszem.',
      name: 'Kovács András',
      product: 'Colombia Huila',
    },
    {
      id: 3,
      stars: 5,
      quote: 'Az előfizetés megváltoztatta a reggeli rutinom. Friss kávé minden nap, egyszerű és kényelmes!',
      name: 'Szabó Eszter',
      product: 'Kenya AA',
    },
  ];

  return (
    <div>
      {/* Hero Banner */}
      <section className="relative h-[500px] overflow-hidden">
        <ImageWithFallback
          src="https://images.unsplash.com/photo-1736813133035-6baf4762fd3d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBiZWFucyUyMGJhcmlzdGElMjBhdG1vc3BoZXJpY3xlbnwxfHx8fDE3NzMzNDgxNjJ8MA&ixlib=rb-4.1.0&q=80&w=1080"
          alt="Coffee Hero"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-black/30">
          <div className="max-w-[--container-max] mx-auto px-4 sm:px-6 h-full flex items-center">
            <div className="max-w-2xl text-white">
              <h1 className="mb-4" style={{ color: 'white' }}>
                Specialty kávé, az asztalodra szállítva.
              </h1>
              <p className="text-xl mb-8 opacity-90">
                Kézzel válogatott, frissen pörkölt kávékülönlegességek Budapestről
              </p>
              <Button variant="primary">
                Fedezd fel kávéinkat <ArrowRight className="ml-2 w-5 h-5 inline" />
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Coffees */}
      <section className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-16">
        <h2 className="text-center mb-12">Kedvenceink</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {featuredCoffees.map((coffee) => (
            <ProductCard key={coffee.id} {...coffee} />
          ))}
        </div>
        <div className="text-center mt-8">
          <Link
            to="/kavek"
            className="inline-flex items-center text-[--color-secondary] hover:underline font-medium"
          >
            Összes kávé <ArrowRight className="ml-1 w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Subscription CTA */}
      <section className="bg-white py-16">
        <div className="max-w-[--container-max] mx-auto px-4 sm:px-6">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div>
              <ImageWithFallback
                src="https://images.unsplash.com/photo-1772200514909-c0ba6cba34f0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjb2ZmZWUlMjBkZWxpdmVyeSUyMHBhY2thZ2V8ZW58MXx8fHwxNzczMzQ4MTY0fDA&ixlib=rb-4.1.0&q=80&w=1080"
                alt="Coffee Delivery"
                className="w-full h-auto rounded-lg shadow-lg"
              />
            </div>
            <div>
              <h2 className="mb-6">Friss kávé minden reggel</h2>
              <p className="text-lg text-[--color-muted] mb-8">
                Napi szállítás Budapesten, 15% kedvezménnyel. Válaszd ki a kedvenc kávédat, mi visszük.
              </p>
              <Button variant="outlined">
                Előfizetés részletei <ArrowRight className="ml-2 w-5 h-5 inline" />
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Story Highlights */}
      <section className="max-w-[--container-max] mx-auto px-4 sm:px-6 py-16">
        <h2 className="text-center mb-12">Sztorik</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {stories.map((story) => (
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
                <span className="inline-block px-3 py-1 bg-[--color-primary] text-white text-xs rounded-full mb-3">
                  {story.category}
                </span>
                <h3 className="mb-2">{story.title}</h3>
                <p className="text-sm text-[--color-muted]">{story.date}</p>
              </div>
            </Link>
          ))}
        </div>
        <div className="text-center mt-8">
          <Link
            to="/sztorik"
            className="inline-flex items-center text-[--color-secondary] hover:underline font-medium"
          >
            Összes sztori <ArrowRight className="ml-1 w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* Testimonials */}
      <section className="bg-white py-16">
        <div className="max-w-[--container-max] mx-auto px-4 sm:px-6">
          <h2 className="text-center mb-12">Mit mondanak vásárlóink</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {testimonials.map((testimonial) => (
              <div key={testimonial.id} className="bg-[--color-background] p-6 rounded-lg shadow-sm">
                <div className="flex gap-1 mb-4">
                  {[...Array(testimonial.stars)].map((_, i) => (
                    <span key={i} className="text-[--color-secondary]">★</span>
                  ))}
                </div>
                <p className="italic text-[--color-text] mb-4">"{testimonial.quote}"</p>
                <p className="font-medium text-[--color-text]">{testimonial.name}</p>
                <p className="text-sm text-[--color-muted]">{testimonial.product}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}