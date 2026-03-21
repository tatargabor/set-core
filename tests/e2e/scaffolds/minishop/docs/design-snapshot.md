# Design Snapshot

File key: 9PH3uS4vWjSj6cUPhTGZSt
Type: make

## Pages & Frames

*Make file (file key: 9PH3uS4vWjSj6cUPhTGZSt)*

## Design Tokens

### Colors (from Tailwind classes)
- `bg-blue-100` (×3)
- `bg-blue-600` (×4)
- `bg-gray-100` (×6)
- `bg-gray-50` (×8)
- `bg-gray-900` (×1)
- `bg-green-100` (×1)
- `bg-white` (×20)
- `text-blue-600` (×12)
- `text-gray-300` (×2)
- `text-gray-500` (×1)
- `text-gray-600` (×20)
- `text-gray-700` (×7)
- `text-gray-900` (×47)
- `text-green-600` (×1)
- `text-red-500` (×1)
- `text-red-600` (×1)
- `text-white` (×5)
### Typography
- `font-bold` (×24)
- `font-medium` (×16)
- `font-semibold` (×18)
- `text-2xl` (×4)
- `text-3xl` (×9)
- `text-4xl` (×3)
- `text-5xl` (×1)
- `text-base` (×1)
- `text-lg` (×3)
- `text-sm` (×22)
- `text-xl` (×6)
### Spacing
- `gap-12` (×1)
- `gap-2` (×11)
- `gap-3` (×6)
- `gap-4` (×2)
- `gap-6` (×3)
- `gap-8` (×2)
- `mb-1` (×4)
- `mb-12` (×1)
- `mb-2` (×6)
- `mb-3` (×4)
- `mb-4` (×4)
- `mb-6` (×13)
- `mb-8` (×6)
- `mt-1` (×2)
- `mt-12` (×1)
- `mt-2` (×1)
- `mt-4` (×1)
- `mt-6` (×4)
- `mx-auto` (×14)
- `p-2` (×3)
- `p-3` (×1)
- `p-4` (×4)
- `p-6` (×6)
- `p-8` (×3)
- `pt-6` (×2)
- `px-3` (×2)
- `px-4` (×7)
- `px-6` (×39)
- `px-8` (×2)
- `py-12` (×1)
- `py-16` (×2)
- `py-2` (×5)
- `py-3` (×5)
- `py-4` (×27)
- `py-6` (×2)
- `py-8` (×9)
- `space-y-4` (×1)
### Borders & Radius
- `border` (×9)
- `border-2` (×1)
- `border-b` (×4)
- `border-gray-200` (×13)
- `border-gray-300` (×3)
- `border-t` (×2)
- `rounded` (×3)
- `rounded-full` (×1)
- `rounded-lg` (×27)
### Shadows
- `shadow-lg` (×1)
- `shadow-md` (×10)
- `shadow-sm` (×2)

## Component Hierarchy

This contains the resource links for all the source files in the Figma Make. Start with App.tsx to understand the code.

## Source Files

### ATTRIBUTIONS.md
```
This Figma Make file includes components from [shadcn/ui](https://ui.shadcn.com/) used under [MIT license](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md).

This Figma Make file includes photos from [Unsplash](https://unsplash.com) used under [license](https://unsplash.com/license).

```

### guidelines/Guidelines.md
```
**Add your own guidelines here**
<!--

System Guidelines

Use this file to provide the AI with rules and guidelines you want it to follow.
This template outlines a few examples of things you can add. You can add your own sections and format it to suit your needs

TIP: More context isn't always better. It can confuse the LLM. Try and add the most important rules you need

# General guidelines

Any general rules you want the AI to follow.
For example:

* Only use absolute positioning when necessary. Opt for responsive and well structured layouts that use flexbox and grid by default
* Refactor code as you go to keep code clean
* Keep file sizes small and put helper functions and components in their own files.

--------------

# Design system guidelines
Rules for how the AI should make generations look like your company's design system

Additionally, if you select a design system to use in the prompt box, you can reference
your design system's components, tokens, variables and components.
For example:

* Use a base font-size of 14px
* Date formats should always be in the format “Jun 10”
* The bottom toolbar should only ever have a maximum of 4 items
* Never use the floating action button with the bottom toolbar
* Chips should always come in sets of 3 or more
* Don't use a dropdown if there are 2 or fewer options

You can also create sub sections and add more specific details
For example:


## Button
The Button component is a fundamental interactive element in our design system, designed to trigger actions or navigate
users through the application. It provides visual feedback and clear affordances to enhance user experience.

### Usage
Buttons should be used for important actions that users need to take, such as form submissions, confirming choices,
or initiating processes. They communicate interactivity and should have clear, action-oriented labels.

### Variants
* Primary Button
  * Purpose : Used for the main action in a section or page
  * Visual Style : Bold, filled with the primary brand color
  * Usage : One primary button per section to guide users toward the most important action
* Secondary Button
  * Purpose : Used for alternative or supporting actions
  * Visual Style : Outlined with the primary color, transparent background
  * Usage : Can appear alongside a primary button for less important actions
* Tertiary Button
  * Purpose : Used for the least important actions
  * Visual Style : Text-only with no border, using primary color
  * Usage : For actions that should be available but not emphasized
-->

```

### package.json
```
{
  "name": "@figma/my-make-file",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "build": "vite build"
  },
  "dependencies": {
    "@emotion/react": "11.14.0",
    "@emotion/styled": "11.14.1",
    "@mui/icons-material": "7.3.5",
    "@mui/material": "7.3.5",
    "@popperjs/core": "2.11.8",
    "@radix-ui/react-accordion": "1.2.3",
    "@radix-ui/react-alert-dialog": "1.1.6",
    "@radix-ui/react-aspect-ratio": "1.1.2",
    "@radix-ui/react-avatar": "1.1.3",
    "@radix-ui/react-checkbox": "1.1.4",
    "@radix-ui/react-collapsible": "1.1.3",
    "@radix-ui/react-context-menu": "2.2.6",
    "@radix-ui/react-dialog": "1.1.6",
    "@radix-ui/react-dropdown-menu": "2.1.6",
    "@radix-ui/react-hover-card": "1.1.6",
    "@radix-ui/react-label": "2.1.2",
    "@radix-ui/react-menubar": "1.1.6",
    "@radix-ui/react-navigation-menu": "1.2.5",
    "@radix-ui/react-popover": "1.1.6",
    "@radix-ui/react-progress": "1.1.2",
    "@radix-ui/react-radio-group": "1.2.3",
    "@radix-ui/react-scroll-area": "1.2.3",
    "@radix-ui/react-select": "2.1.6",
    "@radix-ui/react-separator": "1.1.2",
    "@radix-ui/react-slider": "1.2.3",
    "@radix-ui/react-slot": "1.1.2",
    "@radix-ui/react-switch": "1.1.3",
    "@radix-ui/react-tabs": "1.1.3",
    "@radix-ui/react-toggle-group": "1.1.2",
    "@radix-ui/react-toggle": "1.1.2",
    "@radix-ui/react-tooltip": "1.1.8",
    "canvas-confetti": "1.9.4",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "cmdk": "1.1.1",
    "date-fns": "3.6.0",
    "embla-carousel-react": "8.6.0",
    "input-otp": "1.4.2",
    "lucide-react": "0.487.0",
    "motion": "12.23.24",
    "next-themes": "0.4.6",
    "react-day-picker": "8.10.1",
    "react-dnd": "16.0.1",
    "react-dnd-html5-backend": "16.0.1",
    "react-hook-form": "7.55.0",
    "react-popper": "2.3.0",
    "react-resizable-panels": "2.1.7",
    "react-responsive-masonry": "2.7.1",
    "react-router": "7.13.0",
    "react-slick": "0.31.0",
    "recharts": "2.15.2",
    "sonner": "2.0.3",
    "tailwind-merge": "3.2.0",
    "tw-animate-css": "1.3.8",
    "vaul": "1.1.2"
  },
  "devDependencies": {
    "@tailwindcss/vite": "4.1.12",
    "@vitejs/plugin-react": "4.7.0",
    "tailwindcss": "4.1.12",
    "vite": "6.3.5"
  },
  "peerDependencies": {
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "peerDependenciesMeta": {
    "react": {
      "optional": true
    },
    "react-dom": {
      "optional": true
    }
  },
  "pnpm": {
    "overrides": {
      "vite": "6.3.5"
    }
  }
}

```

### postcss.config.mjs
```
/**
 * PostCSS Configuration
 *
 * Tailwind CSS v4 (via @tailwindcss/vite) automatically sets up all required
 * PostCSS plugins — you do NOT need to include `tailwindcss` or `autoprefixer` here.
 *
 * This file only exists for adding additional PostCSS plugins, if needed.
 * For example:
 *
 * import postcssNested from 'postcss-nested'
 * export default { plugins: [postcssNested()] }
 *
 * Otherwise, you can leave this file empty.
 */
export default {}

```

### src/app/App.tsx
```
import { RouterProvider } from 'react-router';
import { router } from './routes';

export default function App() {
  return <RouterProvider router={router} />;
}

```

### src/app/components/AdminSidebar.tsx
```
import { Link, useLocation } from 'react-router';
import { LayoutDashboard, Package, LogOut } from 'lucide-react';

export function AdminSidebar() {
  const location = useLocation();
  
  const links = [
    { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/admin/products', label: 'Products', icon: Package },
  ];

  return (
    <div className="w-64 bg-gray-900 text-white min-h-screen">
      <div className="p-6">
        <h2 className="text-xl font-bold">Admin Panel</h2>
      </div>
      <nav className="px-3">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <Icon className="w-5 h-5" />
              {link.label}
            </Link>
          );
        })}
        <Link
          to="/admin"
          className="flex items-center gap-3 px-4 py-3 rounded-lg mb-1 text-gray-300 hover:bg-gray-800 transition-colors mt-4"
        >
          <LogOut className="w-5 h-5" />
          Logout
        </Link>
      </nav>
    </div>
  );
}

```

### src/app/components/Navbar.tsx
```
import { Link } from 'react-router';
import { ShoppingCart } from 'lucide-react';

export function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-[1280px] mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-2xl font-bold text-gray-900">
            MiniShop
          </Link>
          <div className="flex items-center gap-8">
            <Link to="/products" className="text-gray-700 hover:text-gray-900 transition-colors">
              Products
            </Link>
            <Link to="/cart" className="text-gray-700 hover:text-gray-900 transition-colors flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" />
              Cart
            </Link>
            <Link to="/orders" className="text-gray-700 hover:text-gray-900 transition-colors">
              Orders
            </Link>
            <Link to="/admin" className="text-gray-700 hover:text-gray-900 transition-colors">
              Admin
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}

export function MobileNavbar() {
  return (
    <nav className="bg-white border-b border-gray-200 shadow-sm">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-gray-900">
            MiniShop
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/cart" className="text-gray-700">
              <ShoppingCart className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}
```

### src/app/components/ProductCard.tsx
```
import { Link } from 'react-router';
import { Product } from '../data/mockData';

interface ProductCardProps {
  product: Product;
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg transition-shadow">
      <div className="aspect-square bg-gray-100">
        <img 
          src={product.image} 
          alt={product.name}
          className="w-full h-full object-cover"
        />
      </div>
      <div className="p-4">
        <h3 className="font-semibold text-lg text-gray-900 mb-1">{product.name}</h3>
        <p className="text-sm text-gray-600 mb-3">{product.shortDescription}</p>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xl font-bold text-gray-900">€{product.price.toFixed(2)}</span>
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            product.inStock 
              ? 'bg-green-100 text-green-800' 
              : 'bg-red-100 text-red-800'
          }`}>
            {product.inStock ? 'In Stock' : 'Out of Stock'}
          </span>
        </div>
        <Link 
          to={`/product/${product.id}`}
          className={`block w-full py-2 px-4 rounded-md text-center font-medium transition-colors ${
            product.inStock
              ? 'bg-blue-600 text-white hover:bg-blue-700'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          View Details
        </Link>
      </div>
    </div>
  );
}

```

### src/app/components/figma/ImageWithFallback.tsx
```
import React, { useState } from 'react'

const ERROR_IMG_SRC =
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODgiIGhlaWdodD0iODgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgc3Ryb2tlPSIjMDAwIiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBvcGFjaXR5PSIuMyIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIzLjciPjxyZWN0IHg9IjE2IiB5PSIxNiIgd2lkdGg9IjU2IiBoZWlnaHQ9IjU2IiByeD0iNiIvPjxwYXRoIGQ9Im0xNiA1OCAxNi0xOCAzMiAzMiIvPjxjaXJjbGUgY3g9IjUzIiBjeT0iMzUiIHI9IjciLz48L3N2Zz4KCg=='

export function ImageWithFallback(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  const [didError, setDidError] = useState(false)

  const handleError = () => {
    setDidError(true)
  }

  const { src, alt, style, className, ...rest } = props

  return didError ? (
    <div
      className={`inline-block bg-gray-100 text-center align-middle ${className ?? ''}`}
      style={style}
    >
      <div className="flex items-center justify-center w-full h-full">
        <img src={ERROR_IMG_SRC} alt="Error loading image" {...rest} data-original-url={src} />
      </div>
    </div>
  ) : (
    <img src={src} alt={alt} className={className} style={style} {...rest} onError={handleError} />
  )
}

```

### src/app/data/mockData.ts
```
export interface Product {
  id: number;
  name: string;
  description: string;
  shortDescription: string;
  price: number;
  inStock: boolean;
  image: string;
  variants?: {
    [key: string]: string[];
  };
}

export interface CartItem {
  product: Product;
  quantity: number;
}

export interface OrderItem {
  productName: string;
  quantity: number;
  price: number;
}

export interface Order {
  id: number;
  date: string;
  status: 'Completed' | 'Pending';
  total: number;
  items: OrderItem[];
}

export const products: Product[] = [
  {
    id: 1,
    name: "Wireless Earbuds Pro",
    shortDescription: "Premium noise-canceling earbuds",
    description: "Experience crystal-clear audio with active noise cancellation. Premium wireless earbuds with 24-hour battery life and premium sound quality.",
    price: 89.99,
    inStock: true,
    image: "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?w=800&q=80",
    variants: {
      Color: ["Black", "White", "Silver"]
    }
  },
  {
    id: 2,
    name: "USB-C Hub 7-in-1",
    shortDescription: "Multi-port connectivity adapter",
    description: "Expand your laptop's capabilities with 7 ports including HDMI, USB 3.0, SD card reader, and more. Perfect for professionals on the go.",
    price: 49.99,
    inStock: true,
    image: "https://images.unsplash.com/photo-1625948515291-69613efd103f?w=800&q=80",
    variants: {
      Color: ["Space Gray", "Silver"]
    }
  },
  {
    id: 3,
    name: "Mechanical Keyboard",
    shortDescription: "RGB backlit gaming keyboard",
    description: "Cherry MX switches with customizable RGB lighting. Durable aluminum frame and programmable keys for the ultimate typing experience.",
    price: 129.99,
    inStock: true,
    image: "https://images.unsplash.com/photo-1595225476474-87563907a212?w=800&q=80",
    variants: {
      "Switch Type": ["Red", "Blue", "Brown"],
      Color: ["Black", "White"]
    }
  },
  {
    id: 4,
    name: "Wireless Mouse",
    shortDescription: "Ergonomic design, 6 buttons",
    description: "Precision optical sensor with adjustable DPI. Ergonomic design for all-day comfort. Works seamlessly across multiple devices.",
    price: 39.99,
    inStock: true,
    image: "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=800&q=80",
    variants: {
      Color: ["Black", "White", "Gray"]
    }
  },
  {
    id: 5,
    name: "Phone Stand Adjustable",
    shortDescription: "Aluminum desktop holder",
    description: "Sleek aluminum stand with 360° rotation and adjustable viewing angles. Compatible with all smartphones and tablets.",
    price: 24.99,
    inStock: true,
    image: "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=800&q=80",
    variants: {
      Color: ["Silver", "Space Gray", "Rose Gold"]
    }
  },
  {
    id: 6,
    name: "4K Webcam",
    shortDescription: "Professional streaming camera",
    description: "Ultra HD 4K resolution with auto-focus and built-in microphone. Perfect for streaming, video calls, and content creation.",
    price: 159.99,
    inStock: false,
    image: "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=800&q=80",
    variants: {
      Resolution: ["1080p", "4K"],
      Color: ["Black", "White"]
    }
  }
];

export const orders: Order[] = [
  {
    id: 1,
    date: "2026-03-10",
    status: "Completed",
    total: 269.97,
    items: [
      { productName: "Wireless Earbuds Pro", quantity: 2, price: 89.99 },
      { productName: "Wireless Mouse", quantity: 1, price: 39.99 },
      { productName: "Phone Stand Adjustable", quantity: 2, price: 24.99 }
    ]
  },
  {
    id: 2,
    date: "2026-03-08",
    status: "Pending",
    total: 179.98,
    items: [
      { productName: "USB-C Hub 7-in-1", quantity: 2, price: 49.99 },
      { productName: "Wireless Mouse", quantity: 2, price: 39.99 }
    ]
  },
  {
    id: 3,
    date: "2026-03-05",
    status: "Completed",
    total: 219.97,
    items: [
      { productName: "Mechanical Keyboard", quantity: 1, price: 129.99 },
      { productName: "Wireless Earbuds Pro", quantity: 1, price: 89.99 }
    ]
  },
  {
    id: 4,
    date: "2026-03-01",
    status: "Completed",
    total: 74.98,
    items: [
      { productName: "Phone Stand Adjustable", quantity: 2, price: 24.99 },
      { productName: "Wireless Mouse", quantity: 1, price: 39.99 }
    ]
  }
];

// Mock cart data
export const initialCart: CartItem[] = [
  { product: products[0], quantity: 1 },
  { product: products[2], quantity: 1 },
  { product: products[4], quantity: 2 }
];
```

### src/app/pages/AdminDashboard.tsx
```
import { AdminSidebar } from '../components/AdminSidebar';
import { Package, ShoppingBag } from 'lucide-react';
import { products, orders } from '../data/mockData';

export function AdminDashboard() {
  const totalProducts = products.length;
  const totalOrders = orders.length;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <AdminSidebar />
      <div className="flex-1">
        <div className="max-w-[1280px] mx-auto px-8 py-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome, Admin</h1>
          <p className="text-gray-600 mb-8">Here's an overview of your store</p>
          
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium mb-1">Total Products</p>
                  <p className="text-4xl font-bold text-gray-900">{totalProducts}</p>
                </div>
                <div className="bg-blue-100 p-4 rounded-lg">
                  <Package className="w-8 h-8 text-blue-600" />
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium mb-1">Total Orders</p>
                  <p className="text-4xl font-bold text-gray-900">{totalOrders}</p>
                </div>
                <div className="bg-green-100 p-4 rounded-lg">
                  <ShoppingBag className="w-8 h-8 text-green-600" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/AdminLogin.tsx
```
import { useState } from 'react';
import { useNavigate, Link } from 'react-router';
import { Lock } from 'lucide-react';

export function AdminLogin() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Mock login - just navigate to dashboard
    navigate('/admin/dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="max-w-[1280px] w-full px-6">
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-md p-8">
          <div className="flex items-center justify-center mb-6">
            <div className="bg-blue-100 p-3 rounded-full">
              <Lock className="w-8 h-8 text-blue-600" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 text-center mb-8">Admin Login</h1>
          <form onSubmit={handleSubmit}>
            <div className="mb-4">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="admin@minishop.com"
                required
              />
            </div>
            <div className="mb-6">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Sign In
            </button>
          </form>
          <div className="mt-6 text-center">
            <Link to="/admin/register" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
              Don't have an account? Register
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/AdminProducts.tsx
```
import { AdminSidebar } from '../components/AdminSidebar';
import { products } from '../data/mockData';
import { Plus, Pencil, Trash2 } from 'lucide-react';

export function AdminProducts() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <AdminSidebar />
      <div className="flex-1">
        <div className="max-w-[1280px] mx-auto px-8 py-8">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Products</h1>
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2">
              <Plus className="w-5 h-5" />
              Add Product
            </button>
          </div>
          
          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Name</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Price</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Stock</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {products.map(product => (
                  <tr key={product.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gray-100 rounded overflow-hidden flex-shrink-0">
                          <img 
                            src={product.image} 
                            alt={product.name}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{product.name}</p>
                          <p className="text-sm text-gray-600">{product.shortDescription}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 font-medium text-gray-900">€{product.price.toFixed(2)}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                        product.inStock
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {product.inStock ? 'In Stock' : 'Out of Stock'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button className="p-2 text-blue-600 hover:bg-blue-50 rounded transition-colors">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

```

### src/app/pages/Cart.tsx
```
import { useState } from 'react';
import { Link } from 'react-router';
import { Navbar } from '../components/Navbar';
import { initialCart } from '../data/mockData';
import { Minus, Plus, Trash2, ShoppingCart } from 'lucide-react';

export function Cart() {
  const [cartItems, setCartItems] = useState(initialCart);

  const updateQuantity = (productId: number, delta: number) => {
    setCartItems(items => 
      items.map(item => 
        item.product.id === productId 
          ? { ...item, quantity: Math.max(1, item.quantity + delta) }
          : item
      )
    );
  };

  const removeItem = (productId: number) => {
    setCartItems(items => items.filter(item => item.product.id !== productId));
  };

  const total = cartItems.reduce((sum, item) => sum + (item.product.price * item.quantity), 0);

  if (cartItems.length === 0) {
    return (
      <div className="min-h-screen bg-white">
        <Navbar />
        <div className="max-w-[1280px] mx-auto px-6 py-16">
          <div className="flex flex-col items-center justify-center py-16">
            <ShoppingCart className="w-24 h-24 text-gray-300 mb-6" />
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Your cart is empty</h2>
            <p className="text-gray-600 mb-6">Add some products to get started</p>
            <Link 
              to="/products"
              className="bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Shopping Cart ({cartItems.length} items)</h1>
        <div className="bg-white rounded-lg shadow-md p-6 mt-6">
          <div className="divide-y divide-gray-200">
            {cartItems.map(item => (
              <div key={item.product.id} className="py-6 flex items-center gap-6">
                <div className="w-24 h-24 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                  <img 
                    src={item.product.image} 
                    alt={item.product.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg text-gray-900">{item.product.name}</h3>
                  <p className="text-sm text-gray-600">{item.product.shortDescription}</p>
                  <p className="text-gray-900 font-medium mt-1">€{item.product.price.toFixed(2)}</p>
                </div>
                <div className="flex items-center gap-3 bg-gray-100 rounded-lg px-3 py-2">
                  <button 
                    onClick={() => updateQuantity(item.product.id, -1)}
                    className="text-gray-600 hover:text-gray-900"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="font-medium w-8 text-center">{item.quantity}</span>
                  <button 
                    onClick={() => updateQuantity(item.product.id, 1)}
                    className="text-gray-600 hover:text-gray-900"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
                <div className="w-24 text-right font-bold text-gray-900">
                  €{(item.product.price * item.quantity).toFixed(2)}
                </div>
                <button 
                  onClick={() => removeItem(item.product.id)}
                  className="text-red-500 hover:text-red-700 transition-colors"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            ))}
          </div>
          <div className="border-t border-gray-200 pt-6 mt-6">
            <div className="flex items-center justify-between mb-6">
              <span className="text-xl font-bold text-gray-900">Total:</span>
              <span className="text-3xl font-bold text-gray-900">€{total.toFixed(2)}</span>
            </div>
            <button className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium text-lg hover:bg-blue-700 transition-colors">
              Place Order
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

### src/app/pages/Index.tsx
```
import { Link } from 'react-router';
import { ShoppingBag, ShoppingCart, Package, Lock, LayoutDashboard, Smartphone } from 'lucide-react';

export function Index() {
  const sections = [
    {
      title: 'Storefront Pages',
      icon: ShoppingBag,
      links: [
        { to: '/products', label: 'Product Grid (Desktop)', description: '3x2 grid, 1280px wide' },
        { to: '/mobile', label: 'Product Grid (Mobile)', description: 'Single column, 375px wide' },
        { to: '/product/1', label: 'Product Detail', description: 'Large image with details, 1280px wide' },
      ]
    },
    {
      title: 'Cart & Orders',
      icon: ShoppingCart,
      links: [
        { to: '/cart', label: 'Shopping Cart', description: 'Cart with 3 items' },
        { to: '/orders', label: 'Orders List', description: 'Table with order history' },
        { to: '/orders/1', label: 'Order Detail', description: 'Detailed view of order #1' },
      ]
    },
    {
      title: 'Admin Pages',
      icon: Lock,
      links: [
        { to: '/admin', label: 'Admin Login', description: 'Centered login card' },
        { to: '/admin/dashboard', label: 'Admin Dashboard', description: 'Dashboard with stats' },
        { to: '/admin/products', label: 'Admin Products', description: 'Product management table' },
      ]
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-[1280px] mx-auto px-6 py-12">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">MiniShop</h1>
          <p className="text-xl text-gray-600">Complete E-Commerce Web Application</p>
          <p className="text-gray-500 mt-2">Navigate to any page below to explore the app</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <div key={section.title} className="bg-white rounded-lg shadow-lg p-6 border border-gray-200">
                <div className="flex items-center gap-3 mb-6">
                  <div className="bg-blue-100 p-2 rounded-lg">
                    <Icon className="w-6 h-6 text-blue-600" />
                  </div>
                  <h2 className="text-xl font-bold text-gray-900">{section.title}</h2>
                </div>
                <div className="space-y-4">
                  {section.links.map((link) => (
                    <Link
                      key={link.to}
                      to={link.to}
                      className="block p-4 bg-gray-50 rounded-lg hover:bg-blue-50 hover:border-blue-200 border border-gray-200 transition-all group"
                    >
                      <p className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">
                        {link.label}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">{link.description}</p>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-12 bg-white rounded-lg shadow-md p-6 border border-gray-200">
          <h3 className="font-bold text-gray-900 mb-3">Features:</h3>
          <ul className="grid grid-cols-2 gap-3 text-gray-600">
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Responsive design (1280px & 375px)
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Product catalog with stock badges
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Shopping cart with quantity controls
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Order management system
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> Admin panel with sidebar navigation
            </li>
            <li className="flex items-center gap-2">
              <span className="text-blue-600">✓</span> shadcn/ui aesthetic with Inter font
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
```

### src/app/pages/MobileProductGrid.tsx
```
import { MobileNavbar } from '../components/Navbar';
import { ProductCard } from '../components/ProductCard';
import { products } from '../data/mockData';

export function MobileProductGrid() {
  return (
    <div className="min-h-screen bg-white w-[375px] mx-auto">
      <MobileNavbar />
      <div className="px-4 py-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Our Products</h1>
        <div className="flex flex-col gap-4">
          {products.map(product => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

### src/app/pages/OrderDetail.tsx
```
import { useParams, Link } from 'react-router';
import { Navbar } from '../components/Navbar';
import { orders } from '../data/mockData';
import { ArrowLeft } from 'lucide-react';

export function OrderDetail() {
  const { id } = useParams();
  const order = orders.find(o => o.id === Number(id));

  if (!order) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-[1280px] mx-auto px-6 py-8">
          <p>Order not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <Link to="/orders" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6">
          <ArrowLeft className="w-4 h-4" />
          Back to Orders
        </Link>
        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Order #{order.id}</h1>
            <span className={`px-4 py-2 rounded-full text-sm font-medium ${
              order.status === 'Completed'
                ? 'bg-green-100 text-green-800'
                : 'bg-yellow-100 text-yellow-800'
            }`}>
              {order.status}
            </span>
          </div>
          <div className="mb-6">
            <p className="text-gray-600">Order Date: {new Date(order.date).toLocaleDateString()}</p>
          </div>
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Product</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Qty</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Price</th>
                  <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Subtotal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {order.items.map((item, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 text-gray-900">{item.productName}</td>
                    <td className="px-6 py-4 text-gray-600">{item.quantity}</td>
                    <td className="px-6 py-4 text-gray-600">€{item.price.toFixed(2)}</td>
                    <td className="px-6 py-4 font-medium text-gray-900">€{(item.price * item.quantity).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end mt-6 pt-6 border-t border-gray-200">
            <div className="text-right">
              <p className="text-gray-600 mb-2">Order Total</p>
              <p className="text-3xl font-bold text-gray-900">€{order.total.toFixed(2)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

### src/app/pages/OrdersList.tsx
```
import { Link } from 'react-router';
import { Navbar } from '../components/Navbar';
import { orders } from '../data/mockData';

export function OrdersList() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Your Orders</h1>
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Order #</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Date</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Status</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Total</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {orders.map(order => (
                <tr key={order.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-gray-900 font-medium">#{order.id}</td>
                  <td className="px-6 py-4 text-gray-600">{new Date(order.date).toLocaleDateString()}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                      order.status === 'Completed'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {order.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-semibold text-gray-900">€{order.total.toFixed(2)}</td>
                  <td className="px-6 py-4">
                    <Link 
                      to={`/orders/${order.id}`}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View Details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
```

### src/app/pages/ProductDetail.tsx
```
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
```

### src/app/pages/ProductGrid.tsx
```
import { Navbar } from '../components/Navbar';
import { ProductCard } from '../components/ProductCard';
import { products } from '../data/mockData';

export function ProductGrid() {
  return (
    <div className="min-h-screen bg-white">
      <Navbar />
      <div className="max-w-[1280px] mx-auto px-6 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Our Products</h1>
        <div className="grid grid-cols-3 gap-6">
          {products.map(product => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </div>
    </div>
  );
}
```

### src/app/routes.tsx
```
import { createBrowserRouter } from 'react-router';
import { Index } from './pages/Index';
import { ProductGrid } from './pages/ProductGrid';
import { MobileProductGrid } from './pages/MobileProductGrid';
import { ProductDetail } from './pages/ProductDetail';
import { Cart } from './pages/Cart';
import { OrdersList } from './pages/OrdersList';
import { OrderDetail } from './pages/OrderDetail';
import { AdminLogin } from './pages/AdminLogin';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminProducts } from './pages/AdminProducts';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Index,
  },
  {
    path: '/products',
    Component: ProductGrid,
  },
  {
    path: '/mobile',
    Component: MobileProductGrid,
  },
  {
    path: '/product/:id',
    Component: ProductDetail,
  },
  {
    path: '/cart',
    Component: Cart,
  },
  {
    path: '/orders',
    Component: OrdersList,
  },
  {
    path: '/orders/:id',
    Component: OrderDetail,
  },
  {
    path: '/admin',
    Component: AdminLogin,
  },
  {
    path: '/admin/dashboard',
    Component: AdminDashboard,
  },
  {
    path: '/admin/products',
    Component: AdminProducts,
  },
]);
```

### src/styles/fonts.css
```
File src/styles/fonts.css not found

Figma Debug UUID: 3fe61929-3006-4291-af99-f67b11112efa
```

### src/styles/index.css
```
@import './fonts.css';
@import './tailwind.css';
@import './theme.css';

```

### src/styles/tailwind.css
```
@import 'tailwindcss' source(none);
@source '../**/*.{js,ts,jsx,tsx}';

@import 'tw-animate-css';

```

### src/styles/theme.css
```
@custom-variant dark (&:is(.dark *));

:root {
  --font-size: 16px;
  --background: #ffffff;
  --foreground: oklch(0.145 0 0);
  --card: #ffffff;
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: #030213;
  --primary-foreground: oklch(1 0 0);
  --secondary: oklch(0.95 0.0058 264.53);
  --secondary-foreground: #030213;
  --muted: #ececf0;
  --muted-foreground: #717182;
  --accent: #e9ebef;
  --accent-foreground: #030213;
  --destructive: #d4183d;
  --destructive-foreground: #ffffff;
  --border: rgba(0, 0, 0, 0.1);
  --input: transparent;
  --input-background: #f3f3f5;
  --switch-background: #cbced4;
  --font-weight-medium: 500;
  --font-weight-normal: 400;
  --ring: oklch(0.708 0 0);
  --chart-1: oklch(0.646 0.222 41.116);
  --chart-2: oklch(0.6 0.118 184.704);
  --chart-3: oklch(0.398 0.07 227.392);
  --chart-4: oklch(0.828 0.189 84.429);
  --chart-5: oklch(0.769 0.188 70.08);
  --radius: 0.625rem;
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: #030213;
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --card: oklch(0.145 0 0);
  --card-foreground: oklch(0.985 0 0);
  --popover: oklch(0.145 0 0);
  --popover-foreground: oklch(0.985 0 0);
  --primary: oklch(0.985 0 0);
  --primary-foreground: oklch(0.205 0 0);
  --secondary: oklch(0.269 0 0);
  --secondary-foreground: oklch(0.985 0 0);
  --muted: oklch(0.269 0 0);
  --muted-foreground: oklch(0.708 0 0);
  --accent: oklch(0.269 0 0);
  --accent-foreground: oklch(0.985 0 0);
  --destructive: oklch(0.396 0.141 25.723);
  --destructive-foreground: oklch(0.637 0.237 25.331);
  --border: oklch(0.269 0 0);
  --input: oklch(0.269 0 0);
  --ring: oklch(0.439 0 0);
  --font-weight-medium: 500;
  --font-weight-normal: 400;
  --chart-1: oklch(0.488 0.243 264.376);
  --chart-2: oklch(0.696 0.17 162.48);
  --chart-3: oklch(0.769 0.188 70.08);
  --chart-4: oklch(0.627 0.265 303.9);
  --chart-5: oklch(0.645 0.246 16.439);
  --sidebar: oklch(0.205 0 0);
  --sidebar-foreground: oklch(0.985 0 0);
  --sidebar-primary: oklch(0.488 0.243 264.376);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.269 0 0);
  --sidebar-accent-foreground: oklch(0.985 0 0);
  --sidebar-border: oklch(0.269 0 0);
  --sidebar-ring: oklch(0.439 0 0);
}

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-destructive-foreground: var(--destructive-foreground);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-input-background: var(--input-background);
  --color-switch-background: var(--switch-background);
  --color-ring: var(--ring);
  --color-chart-1: var(--chart-1);
  --color-chart-2: var(--chart-2);
  --color-chart-3: var(--chart-3);
  --color-chart-4: var(--chart-4);
  --color-chart-5: var(--chart-5);
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --color-sidebar: var(--sidebar);
  --color-sidebar-foreground: var(--sidebar-foreground);
  --color-sidebar-primary: var(--sidebar-primary);
  --color-sidebar-primary-foreground: var(--sidebar-primary-foreground);
  --color-sidebar-accent: var(--sidebar-accent);
  --color-sidebar-accent-foreground: var(--sidebar-accent-foreground);
  --color-sidebar-border: var(--sidebar-border);
  --color-sidebar-ring: var(--sidebar-ring);
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }

  body {
    @apply bg-background text-foreground;
  }

  /**
  * Default typography styles for HTML elements (h1-h4, p, label, button, input).
  * These are in @layer base, so Tailwind utility classes (like text-sm, text-lg) automatically override them.
  */

  html {
    font-size: var(--font-size);
  }

  h1 {
    font-size: var(--text-2xl);
    font-weight: var(--font-weight-medium);
    line-height: 1.5;
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: var(--font-weight-medium);
    line-height: 1.5;
  }

  h3 {
    font-size: var(--text-lg);
    font-weight: var(--font-weight-medium);
    line-height: 1.5;
  }

  h4 {

... (448 chars truncated)
```

### vite.config.ts
```
import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    // The React and Tailwind plugins are both required for Make, even if
    // Tailwind is not being actively used – do not remove them
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      // Alias @ to the src directory
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],
})

```

### UI Library Components
*48 shadcn/ui primitives available in `sources/` (not inlined):*

- `src/app/components/ui/accordion.tsx`
- `src/app/components/ui/alert-dialog.tsx`
- `src/app/components/ui/alert.tsx`
- `src/app/components/ui/aspect-ratio.tsx`
- `src/app/components/ui/avatar.tsx`
- `src/app/components/ui/badge.tsx`
- `src/app/components/ui/breadcrumb.tsx`
- `src/app/components/ui/button.tsx`
- `src/app/components/ui/calendar.tsx`
- `src/app/components/ui/card.tsx`
- `src/app/components/ui/carousel.tsx`
- `src/app/components/ui/chart.tsx`
- `src/app/components/ui/checkbox.tsx`
- `src/app/components/ui/collapsible.tsx`
- `src/app/components/ui/command.tsx`
- `src/app/components/ui/context-menu.tsx`
- `src/app/components/ui/dialog.tsx`
- `src/app/components/ui/drawer.tsx`
- `src/app/components/ui/dropdown-menu.tsx`
- `src/app/components/ui/form.tsx`
- `src/app/components/ui/hover-card.tsx`
- `src/app/components/ui/input-otp.tsx`
- `src/app/components/ui/input.tsx`
- `src/app/components/ui/label.tsx`
- `src/app/components/ui/menubar.tsx`
- `src/app/components/ui/navigation-menu.tsx`
- `src/app/components/ui/pagination.tsx`
- `src/app/components/ui/popover.tsx`
- `src/app/components/ui/progress.tsx`
- `src/app/components/ui/radio-group.tsx`
- `src/app/components/ui/resizable.tsx`
- `src/app/components/ui/scroll-area.tsx`
- `src/app/components/ui/select.tsx`
- `src/app/components/ui/separator.tsx`
- `src/app/components/ui/sheet.tsx`
- `src/app/components/ui/sidebar.tsx`
- `src/app/components/ui/skeleton.tsx`
- `src/app/components/ui/slider.tsx`
- `src/app/components/ui/sonner.tsx`
- `src/app/components/ui/switch.tsx`
- `src/app/components/ui/table.tsx`
- `src/app/components/ui/tabs.tsx`
- `src/app/components/ui/textarea.tsx`
- `src/app/components/ui/toggle-group.tsx`
- `src/app/components/ui/toggle.tsx`
- `src/app/components/ui/tooltip.tsx`
- `src/app/components/ui/use-mobile.ts`
- `src/app/components/ui/utils.ts`