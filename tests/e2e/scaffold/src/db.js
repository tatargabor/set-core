const Database = require('better-sqlite3');

const DB_PATH = process.env.DATABASE_PATH || './minishop.db';

const db = new Database(DB_PATH);

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1
  );

  CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    total REAL,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER,
    price REAL
  );

  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

// Seed products if empty
const count = db.prepare('SELECT COUNT(*) as cnt FROM products').get();
if (count.cnt === 0) {
  const insert = db.prepare('INSERT INTO products (name, price, stock) VALUES (?, ?, ?)');
  insert.run('Laptop', 299999, 10);
  insert.run('Egér', 4999, 50);
  insert.run('Billentyűzet', 12999, 30);
}

module.exports = db;
