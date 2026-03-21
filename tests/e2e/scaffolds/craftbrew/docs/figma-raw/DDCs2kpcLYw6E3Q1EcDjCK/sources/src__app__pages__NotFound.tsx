import { Link } from 'react-router';
import { Coffee } from 'lucide-react';
import { Button } from '../components/Button';

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <Coffee className="w-32 h-32 mx-auto text-[--color-muted] mb-6 opacity-50" />
        <h1 className="mb-4">Hoppá! Ez az oldal nem található</h1>
        <p className="text-[--color-muted] mb-8">
          A keresett oldal nem létezik vagy átköltözött.
        </p>
        <Link to="/">
          <Button variant="primary">Vissza a főoldalra</Button>
        </Link>
      </div>
    </div>
  );
}
