import sqlite3
import os

# Use /tmp on Render (writable), or local directory for development
if os.environ.get("RENDER"):
    DB_PATH = "/tmp/expenses.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            amount      REAL    NOT NULL CHECK (amount > 0),
            category_id INTEGER NOT NULL,
            description TEXT,
            date        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );
        CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
        CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
    """)
    default_categories = [
        "Food", "Transport", "Housing", "Utilities",
        "Entertainment", "Health", "Shopping", "Education", "Other"
    ]
    for cat in default_categories:
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
    conn.commit()
    conn.close()
    print(f"✓ Database ready at {DB_PATH}")
