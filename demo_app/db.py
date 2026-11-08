import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    year INTEGER NOT NULL,
    pages INTEGER NOT NULL,
    summary TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 10
);
CREATE TABLE IF NOT EXISTS cart_items (
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, book_id)
);
"""

BOOKS = [
    ("The Alchemist", "Paulo Coelho", "Fiction", 42.0, 1988, 208,
     "A shepherd boy travels from Spain to the Egyptian desert in search of a treasure, and learns to listen to his heart."),
    ("Mountains Echoed", "Khaled Hosseini", "Fiction", 55.0, 2013, 404,
     "A story of family, sacrifice and the choices that echo across generations and continents."),
    ("Cities of Salt", "Abdul Rahman Munif", "Fiction", 61.0, 1984, 627,
     "A sweeping novel about a desert community changed forever by the arrival of oil."),
    ("Sapiens", "Yuval Noah Harari", "History", 68.0, 2011, 443,
     "A short history of humankind, from the first humans to the age of artificial intelligence."),
    ("The Muqaddimah", "Ibn Khaldun", "History", 79.0, 1377, 560,
     "A landmark work on history, society and economics, written six centuries before its time."),
    ("Atomic Habits", "James Clear", "Self-development", 49.0, 2018, 320,
     "Small changes, remarkable results: a practical way to build good habits and break bad ones."),
    ("Deep Work", "Cal Newport", "Self-development", 46.0, 2016, 296,
     "Rules for focused success in a distracted world."),
    ("Clean Code", "Robert C. Martin", "Technology", 89.0, 2008, 464,
     "A handbook of agile software craftsmanship: how to write code that other people can read."),
    ("The Pragmatic Programmer", "Andrew Hunt", "Technology", 85.0, 1999, 352,
     "Practical advice for developers who want to care about their craft."),
    ("Designing Data-Intensive Applications", "Martin Kleppmann", "Technology", 112.0, 2017, 616,
     "The big ideas behind reliable, scalable and maintainable systems."),
    ("A Brief History of Time", "Stephen Hawking", "Science", 52.0, 1988, 256,
     "From the Big Bang to black holes, explained for the curious reader."),
    ("The Selfish Gene", "Richard Dawkins", "Science", 58.0, 1976, 360,
     "A classic that reframed how we think about evolution and the role of genes."),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO books (title, author, category, price, year, pages, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            BOOKS,
        )
        db.execute(
            "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
            ("sara@example.com", "Sara", generate_password_hash("books2024")),
        )
        db.commit()
