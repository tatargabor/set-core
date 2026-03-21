import { Outlet } from 'react-router';
import { Header } from './Header';
import { Footer } from './Footer';
import { PromoBanner } from './PromoBanner';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <PromoBanner />
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}