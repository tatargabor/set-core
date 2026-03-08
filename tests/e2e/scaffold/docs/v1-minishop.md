# MiniShop API v1 — Feature Roadmap

> Updated: 2026-03-08

## 1. v0 Status

| Feature | Status |
|---|---|
| Health endpoint (`GET /api/health`) | ✅ Done |
| Database schema (all tables) | ✅ Done |
| Error handler middleware | ✅ Done |

## 2. Feature Roadmap

### Priority 1 — Core CRUD

#### 2.1 Products CRUD (`products-crud`)

Full CRUD for the products catalog.

- `GET /api/products` — list all products
- `GET /api/products/:id` — get single product
- `POST /api/products` — create product (name, price, stock)
- `PUT /api/products/:id` — update product
- `DELETE /api/products/:id` — delete product

**Data model:** Uses existing `products` table (id, name, price, stock, created_at).

**Acceptance criteria:**
- All 5 endpoints work and return correct status codes (200, 201, 404)
- `npm test` passes with tests covering each endpoint
- Validation: name required, price > 0, stock >= 0

**Files:** `src/routes/products.js`, `tests/products.test.js`

### Priority 2 — Shopping

#### 2.2 Cart (`cart`)

> depends_on: products-crud

Session-based shopping cart.

- `GET /api/cart` — list cart items for current session (with product details)
- `POST /api/cart` — add item to cart (product_id, quantity)
- `DELETE /api/cart/:id` — remove item from cart

**Data model:** Uses existing `cart_items` table (id, session_id, product_id, quantity). Session ID from `session_id` cookie (generate UUID if missing).

**Acceptance criteria:**
- Cart operations work with session cookies
- Adding a product that doesn't exist returns 404
- Adding a product already in cart updates quantity
- `npm test` passes

**Files:** `src/routes/cart.js`, `tests/cart.test.js`

#### 2.3 Orders (`orders`)

> depends_on: cart, products-crud

Convert cart to order with stock management.

- `POST /api/orders` — create order from current cart (cart items → order, clear cart, decrement stock)
- `GET /api/orders` — list orders for current session
- `GET /api/orders/:id` — get order details with items

**Data model:** Uses existing `orders` and `order_items` tables. Order creation runs in a transaction: insert order → copy cart items to order_items with current prices → decrement product stock → clear cart.

**Acceptance criteria:**
- Empty cart returns 400
- Insufficient stock returns 400
- Successful order decrements stock and clears cart
- Order total is calculated from product prices × quantities
- `npm test` passes

**Files:** `src/routes/orders.js`, `tests/orders.test.js`

### Priority 3 — Security

#### 2.4 Auth / JWT (`auth`)

> depends_on: products-crud, cart, orders

Cross-cutting authentication. Runs last because it modifies existing routes by adding auth middleware. NOTE: scope overlap warnings with products-crud, cart, orders are expected and intentional.

- `POST /api/register` — create user (email, password), return JWT
- `POST /api/login` — authenticate user, return JWT

**Auth middleware:** `src/middleware/auth.js` verifies JWT from `Authorization: Bearer <token>` header. Applied to write operations (POST/PUT/DELETE) on products, cart, orders. GET endpoints remain public.

**Data model:** Uses existing `users` table (id, email, password_hash, created_at). Passwords hashed with bcryptjs.

**Acceptance criteria:**
- Registration validates email uniqueness, returns JWT
- Login with wrong password returns 401
- Protected endpoints return 401 without valid token
- GET endpoints work without auth
- `npm test` passes

**Files:** `src/routes/auth.js`, `src/middleware/auth.js`, `tests/auth.test.js`

## Orchestrator Directives

- max_parallel: 2
- smoke_command: npm test
- smoke_blocking: true
- test_command: npm test
- merge_policy: checkpoint
- auto_replan: true
