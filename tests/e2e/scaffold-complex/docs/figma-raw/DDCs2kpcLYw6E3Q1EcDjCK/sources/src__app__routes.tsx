import { createBrowserRouter } from "react-router";
import Home from "./pages/Home";
import ProductCatalog from "./pages/ProductCatalog";
import ProductDetail from "./pages/ProductDetail";
import Cart from "./pages/Cart";
import Checkout from "./pages/Checkout";
import SubscriptionWizard from "./pages/SubscriptionWizard";
import UserDashboard from "./pages/UserDashboard";
import AdminDashboard from "./pages/AdminDashboard";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Stories from "./pages/Stories";
import StoryDetail from "./pages/StoryDetail";
import NotFound from "./pages/NotFound";
import Layout from "./components/Layout";

// Admin Pages
import AdminProducts from "./pages/admin/AdminProducts";
import AdminOrders from "./pages/admin/AdminOrders";
import AdminDeliveries from "./pages/admin/AdminDeliveries";
import AdminCoupons from "./pages/admin/AdminCoupons";
import AdminPromoDays from "./pages/admin/AdminPromoDays";
import AdminGiftCards from "./pages/admin/AdminGiftCards";
import AdminReviews from "./pages/admin/AdminReviews";
import AdminStories from "./pages/admin/AdminStories";
import AdminSubscriptions from "./pages/admin/AdminSubscriptions";

// User Pages
import UserProfile from "./pages/user/UserProfile";
import UserAddresses from "./pages/user/UserAddresses";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Home },
      { path: "kavek", Component: ProductCatalog },
      { path: "kavek/:id", Component: ProductDetail },
      { path: "kosar", Component: Cart },
      { path: "penztar", Component: Checkout },
      { path: "elofizetés", Component: SubscriptionWizard },
      { path: "fiokom", Component: UserProfile },
      { path: "fiokom/cimeim", Component: UserAddresses },
      { path: "admin", Component: AdminDashboard },
      { path: "admin/termekek", Component: AdminProducts },
      { path: "admin/rendelesek", Component: AdminOrders },
      { path: "admin/szallitas", Component: AdminDeliveries },
      { path: "admin/kuponok", Component: AdminCoupons },
      { path: "admin/promo-napok", Component: AdminPromoDays },
      { path: "admin/ajandekkartyak", Component: AdminGiftCards },
      { path: "admin/ertekelesek", Component: AdminReviews },
      { path: "admin/sztorik", Component: AdminStories },
      { path: "admin/elofizetesek", Component: AdminSubscriptions },
      { path: "sztorik", Component: Stories },
      { path: "sztorik/:slug", Component: StoryDetail },
      { path: "belepes", Component: Login },
      { path: "regisztracio", Component: Register },
      { path: "*", Component: NotFound },
    ],
  },
]);