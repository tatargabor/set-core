# Design Brief

Per-page visual specifications for implementing agents.
Color palette: blue-600 primary actions, gray-900 text, gray-50/100 backgrounds, green/red status badges.
All storefront pages use Navbar; admin pages use dark AdminSidebar (bg-gray-900).
Container: max-w-[1280px] mx-auto px-6. Currency: EUR (€).

## Page: Product Grid

Route: /products
Background: bg-white

Sections (top to bottom):

1. Navbar (shared component)

2. Page Title
   - Padding: py-8
   - H1: "Our Products" — text-3xl font-bold text-gray-900 mb-8

3. Product Grid
   - Grid: grid-cols-3 gap-6
   - Each item: ProductCard component (shared)
   - 6 products: Wireless Earbuds Pro (€89.99), USB-C Hub (€49.99), Mechanical Keyboard (€129.99), Wireless Mouse (€39.99), Phone Stand (€24.99), 4K Webcam (€159.99, out of stock)

## Page: Product Detail

Route: /product/:id
Background: bg-white

Sections:

1. Navbar (shared component)

2. Back Link
   - inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6
   - ArrowLeft icon (lucide-react) + "Back to Products"
   - Links to /products

3. Product Card
   - bg-white rounded-lg shadow-md p-8 grid grid-cols-2 gap-12
   - Left: aspect-square bg-gray-100 rounded-lg with product image (object-cover)
   - Right column (flex flex-col):
     * H1: product name — text-3xl font-bold text-gray-900 mb-4
     * Description: text-gray-600 mb-6 leading-relaxed
     * Price: text-4xl font-bold text-gray-900 mb-4 — format "€XX.XX"
     * Stock badge: px-4 py-2 rounded-full text-sm font-medium
       - In Stock: bg-green-100 text-green-800
       - Out of Stock: bg-red-100 text-red-800
     * Variant selectors: RadioGroup (shadcn/ui) per variant type
       - Label: text-base font-semibold text-gray-900 mb-3
       - Options: pill-style labels with border-2 border-gray-300 rounded-lg
       - Selected: border-blue-600 bg-blue-50 text-blue-900
       - Variants: Color (Black/White/Silver), Switch Type (Red/Blue/Brown)
     * "Add to Cart" button: w-full py-3 px-6 rounded-lg font-medium text-lg bg-blue-600 text-white hover:bg-blue-700
     * Disabled (out of stock): bg-gray-300 text-gray-500 cursor-not-allowed, text "Out of Stock"

## Page: Shopping Cart

Route: /cart
Background: bg-white

Sections:

1. Navbar (shared component)

2. Page Header
   - H1: "Shopping Cart (N items)" — text-3xl font-bold text-gray-900 mb-2

3. Cart Items
   - bg-white rounded-lg shadow-md p-6 mt-6
   - divide-y divide-gray-200
   - Each item row: py-6 flex items-center gap-6
     * Image: w-24 h-24 bg-gray-100 rounded-lg overflow-hidden, object-cover
     * Details (flex-1): product name (font-semibold text-lg text-gray-900), short description (text-sm text-gray-600), price (text-gray-900 font-medium)
     * Quantity controls: bg-gray-100 rounded-lg px-3 py-2 flex items-center gap-3
       - Minus button (Minus icon), quantity (font-medium w-8 text-center), Plus button (Plus icon)
     * Line total: w-24 text-right font-bold text-gray-900
     * Remove: Trash2 icon text-red-500 hover:text-red-700

4. Cart Footer
   - border-t border-gray-200 pt-6 mt-6
   - Total row: flex justify-between, "Total:" text-xl font-bold, total amount text-3xl font-bold
   - "Place Order" button: w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium text-lg

5. Empty State (when cart is empty)
   - Centered: flex-col items-center justify-center py-16
   - ShoppingCart icon: w-24 h-24 text-gray-300 mb-6
   - "Your cart is empty" — text-2xl font-bold text-gray-900
   - "Add some products to get started" — text-gray-600 mb-6
   - "Continue Shopping" link: bg-blue-600 text-white px-6 py-3 rounded-lg → /products

## Page: Orders List

Route: /orders
Background: bg-white

Sections:

1. Navbar (shared component)

2. Page Title
   - H1: "Your Orders" — text-3xl font-bold text-gray-900 mb-8

3. Orders Table
   - bg-white rounded-lg shadow-md overflow-hidden
   - Table with 5 columns:
     * Header: bg-gray-50 border-b border-gray-200
     * Header cells: px-6 py-4 text-left text-sm font-semibold text-gray-900
     * Columns: Order # | Date | Status | Total | Actions
   - Body rows: divide-y divide-gray-200, hover:bg-gray-50
     * Order #: text-gray-900 font-medium, format "#N"
     * Date: text-gray-600, toLocaleDateString()
     * Status badge: px-3 py-1 rounded-full text-xs font-medium
       - Completed: bg-green-100 text-green-800
       - Pending: bg-yellow-100 text-yellow-800
     * Total: font-semibold text-gray-900, format "€XX.XX"
     * Actions: "View Details" link text-blue-600 hover:text-blue-800 font-medium → /orders/:id

## Page: Order Detail

Route: /orders/:id
Background: bg-white

Sections:

1. Navbar (shared component)

2. Back Link
   - text-gray-600 hover:text-gray-900, ArrowLeft icon + "Back to Orders" → /orders

3. Order Card
   - bg-white rounded-lg shadow-md p-8
   - Header: flex justify-between items-center mb-8
     * H1: "Order #N" — text-3xl font-bold text-gray-900
     * Status badge: px-4 py-2 rounded-full text-sm font-medium (same colors as Orders List)
   - Order date: text-gray-600 mb-6
   - Items table: border border-gray-200 rounded-lg overflow-hidden
     * Header: bg-gray-50, columns: Product | Qty | Price | Subtotal
     * Header cells: px-6 py-4 text-left text-sm font-semibold text-gray-900
     * Body: divide-y divide-gray-200
     * Subtotal per line: font-medium text-gray-900
   - Total section: flex justify-end mt-6 pt-6 border-t border-gray-200
     * "Order Total" label: text-gray-600
     * Total amount: text-3xl font-bold text-gray-900

## Page: Admin Login

Route: /admin
Background: bg-gray-100
Layout: flex items-center justify-center min-h-screen

Sections:

1. Login Card
   - max-w-md mx-auto bg-white rounded-lg shadow-md p-8
   - Lock icon: bg-blue-100 p-3 rounded-full, Lock lucide icon w-8 h-8 text-blue-600, centered
   - H1: "Admin Login" — text-2xl font-bold text-gray-900 text-center mb-8
   - Form fields:
     * Email: label "Email Address" (text-sm font-medium text-gray-700), input with border border-gray-300 rounded-lg, placeholder "admin@minishop.com"
     * Password: label "Password", same styling, placeholder dots
     * Focus state: focus:ring-2 focus:ring-blue-500 focus:border-transparent
   - "Sign In" button: w-full bg-blue-600 text-white py-3 rounded-lg font-medium
   - Footer: "Don't have an account? Register" link text-blue-600 text-sm, centered

## Page: Admin Dashboard

Route: /admin/dashboard
Background: bg-gray-50
Layout: flex min-h-screen (sidebar + content)

Sections:

1. AdminSidebar — left side
   - DARK theme: w-64 bg-gray-900 text-white min-h-screen
   - Header: p-6, "Admin Panel" — text-xl font-bold
   - Nav links: px-3, each link px-4 py-3 rounded-lg mb-1
     * Active: bg-blue-600 text-white
     * Inactive: text-gray-300 hover:bg-gray-800
     * Icons: LayoutDashboard, Package (lucide-react), w-5 h-5
   - Links: Dashboard (/admin/dashboard), Products (/admin/products)
   - Logout: text-gray-300 hover:bg-gray-800, LogOut icon, mt-4

2. Main Content (flex-1)
   - Container: max-w-[1280px] mx-auto px-8 py-8
   - H1: "Welcome, Admin" — text-3xl font-bold text-gray-900 mb-2
   - Subtitle: "Here's an overview of your store" — text-gray-600 mb-8
   - Stats grid: grid-cols-2 gap-6
     * Each stat card: bg-white rounded-lg shadow-md p-6 border border-gray-200
       - Layout: flex items-center justify-between
       - Left: label (text-gray-600 text-sm font-medium mb-1) + value (text-4xl font-bold text-gray-900)
       - Right: icon container (bg-blue-100/bg-green-100 p-4 rounded-lg) + icon (w-8 h-8)
     * Card 1: "Total Products" — Package icon (text-blue-600, bg-blue-100)
     * Card 2: "Total Orders" — ShoppingBag icon (text-green-600, bg-green-100)

## Page: Admin Products

Route: /admin/products
Background: bg-gray-50
Layout: flex min-h-screen (sidebar + content)

Sections:

1. AdminSidebar — left side
   - DARK theme: w-64 bg-gray-900 text-white min-h-screen
   - Header: p-6, "Admin Panel" — text-xl font-bold
   - Nav links: px-3, each link px-4 py-3 rounded-lg mb-1
     * Active: bg-blue-600 text-white
     * Inactive: text-gray-300 hover:bg-gray-800
     * Icons: LayoutDashboard, Package (lucide-react), w-5 h-5
   - Links: Dashboard (/admin/dashboard), Products (/admin/products)
   - Logout: text-gray-300 hover:bg-gray-800, LogOut icon, mt-4

2. Main Content (flex-1)
   - Container: max-w-[1280px] mx-auto px-8 py-8
   - Header row: flex items-center justify-between mb-8
     * H1: "Products" — text-3xl font-bold text-gray-900
     * "Add Product" button: bg-blue-600 text-white px-4 py-2 rounded-lg font-medium, Plus icon + text
   - Products table: bg-white rounded-lg shadow-md overflow-hidden
     * Header: bg-gray-50 border-b border-gray-200
     * Columns: Name | Price | Stock | Actions
     * Name cell: flex items-center gap-3
       - Thumbnail: w-12 h-12 bg-gray-100 rounded, object-cover
       - Text: product name (font-medium text-gray-900) + short description (text-sm text-gray-600)
     * Price: font-medium text-gray-900, format "€XX.XX"
     * Stock badge: same as Product Grid (green/red pill)
     * Actions: flex items-center gap-2
       - Edit: Pencil icon p-2 text-blue-600 hover:bg-blue-50 rounded
       - Delete: Trash2 icon p-2 text-red-600 hover:bg-red-50 rounded

## Shared Components

### Navbar
- Used on: Product Grid, Product Detail, Cart, Orders List, Order Detail
- bg-white border-b border-gray-200 shadow-sm
- Container: max-w-[1280px] mx-auto px-6 py-4
- Layout: flex items-center justify-between
- Left: "MiniShop" logo — text-2xl font-bold text-gray-900, links to /
- Right: nav links (Products, Cart, Orders, Admin) — text-gray-700 hover:text-gray-900
- Cart link has ShoppingCart icon (w-5 h-5) + "Cart" text
- Mobile variant (MobileNavbar): px-4 py-3, logo text-xl, only cart icon (no text links)

### AdminSidebar
- Used on: Admin Dashboard, Admin Products
- DARK theme: w-64 bg-gray-900 text-white min-h-screen
- Header: p-6, "Admin Panel" — text-xl font-bold
- Nav links: px-3, each link px-4 py-3 rounded-lg mb-1
  * Active: bg-blue-600 text-white
  * Inactive: text-gray-300 hover:bg-gray-800
  * Icons: LayoutDashboard, Package (lucide-react), w-5 h-5
- Links: Dashboard (/admin/dashboard), Products (/admin/products)
- Logout: text-gray-300 hover:bg-gray-800, LogOut icon, mt-4, links to /admin

### ProductCard
- Used on: Product Grid, Mobile Product Grid
- bg-white rounded-lg shadow-md overflow-hidden border border-gray-200 hover:shadow-lg
- Image: aspect-square bg-gray-100, object-cover
- Content: p-4
  * Name: font-semibold text-lg text-gray-900 mb-1
  * Description: text-sm text-gray-600 mb-3
  * Price row: flex justify-between — price text-xl font-bold, stock badge (rounded-full text-xs)
  * "View Details" link: block w-full py-2 px-4 rounded-md text-center font-medium
    - In stock: bg-blue-600 text-white hover:bg-blue-700
    - Out of stock: bg-gray-300 text-gray-500 cursor-not-allowed
