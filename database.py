import sqlite3

DB_NAME = "client.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ---------------- CLIENTS TABLE ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        company TEXT
    )
    """)

    # ---------------- PARTNERS TABLE (NEW) ----------------
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE,
        phone TEXT,
        company TEXT
    )
    """)

    # ---------------- USERS TABLE ----------------
    # (for login / admin / staff / roles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# Run this once when file is executed directly
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")