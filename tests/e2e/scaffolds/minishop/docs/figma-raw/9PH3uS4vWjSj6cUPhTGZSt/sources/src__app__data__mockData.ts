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