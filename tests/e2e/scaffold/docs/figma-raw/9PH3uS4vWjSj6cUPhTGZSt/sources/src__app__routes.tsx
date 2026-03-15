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