import { X } from 'lucide-react';
import { useState } from 'react';

export function PromoBanner() {
  const [isVisible, setIsVisible] = useState(true);

  if (!isVisible) return null;

  return (
    <div className="bg-[--color-secondary] text-white py-3 px-4 relative">
      <div className="max-w-[--container-max] mx-auto text-center">
        <p className="font-medium">
          🎉 A CraftBrew 1 éves! 20% kedvezmény mindenből!
        </p>
      </div>
      <button
        onClick={() => setIsVisible(false)}
        className="absolute right-4 top-1/2 -translate-y-1/2 p-1 hover:bg-white/20 rounded"
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}
