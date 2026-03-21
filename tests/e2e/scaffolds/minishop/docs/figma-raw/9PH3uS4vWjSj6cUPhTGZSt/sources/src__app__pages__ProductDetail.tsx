import { useParams, Link } from 'react-router';
import { useState } from 'react';
import { Navbar } from '../components/Navbar';
import { products } from '../data/mockData';
import { ArrowLeft } from 'lucide-react';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { Label } from '../components/ui/label';

export function ProductDetail() {
  const { id } = useParams();
  const product = products.find(p => p.id === Number(id));
  
  // Initialize selected variants with first option of each variant type
  const [selectedVariants, setSelectedVariants] = useState<{ [key: string]: string }>(() => {
    if (!product?.variants) return {};
    const initial: { [key: string]: string } = {};
    Object.entries(product.variants).forEach(([key, values]) => {
      initial[key] = values[0];
    });
    return initial;
  });

  if (!product) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          <p>Product not found</p>
        </div>
      </div>
    );
  }

  const handleVariantChange = (variantType: string, value: string) => {
    setSelectedVariants(prev => ({
      ...prev,
      [variantType]: value
    }));
  };

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <Link to="/products" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Products
        </Link>
        <div className="bg-white rounded-lg shadow-md p-8 grid grid-cols-2 gap-12">
          <div className="aspect-square bg-gray-100 rounded-lg overflow-hidden">
            <img 
              src={product.image} 
              alt={product.name}
              className="w-full h-full object-cover"
            />
          </div>
          <div className="flex flex-col">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">{product.name}</h1>
            <p className="text-gray-600 mb-6 leading-relaxed">{product.description}</p>
            <div className="text-4xl font-bold text-gray-900 mb-4">€{product.price.toFixed(2)}</div>
            <div className="mb-6">
              <span className={`inline-block px-4 py-2 rounded-full text-sm font-medium ${
                product.inStock 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {product.inStock ? 'In Stock' : 'Out of Stock'}
              </span>
            </div>

            {/* Variant Selectors */}
            {product.variants && Object.entries(product.variants).map(([variantType, options]) => (
              <div key={variantType} className="mb-6">
                <Label className="text-base font-semibold text-gray-900 mb-3 block">
                  {variantType}
                </Label>
                <RadioGroup 
                  value={selectedVariants[variantType]} 
                  onValueChange={(value) => handleVariantChange(variantType, value)}
                  className="flex flex-wrap gap-3"
                >
                  {options.map((option) => (
                    <div key={option} className="flex items-center">
                      <RadioGroupItem 
                        value={option} 
                        id={`${variantType}-${option}`}
                        className="peer sr-only"
                      />
                      <Label
                        htmlFor={`${variantType}-${option}`}
                        className="flex items-center justify-center px-4 py-2 border-2 border-gray-300 rounded-lg cursor-pointer transition-all hover:border-blue-500 peer-data-[state=checked]:border-blue-600 peer-data-[state=checked]:bg-blue-50 peer-data-[state=checked]:text-blue-900 min-w-[80px] text-center"
                      >
                        {option}
                      </Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
            ))}

            <button 
              disabled={!product.inStock}
              className={`w-full py-3 px-6 rounded-lg font-medium text-lg transition-colors ${
                product.inStock
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {product.inStock ? 'Add to Cart' : 'Out of Stock'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}