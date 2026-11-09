import os
import textwrap
from functools import wraps

from flask import Flask, Response, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from . import config
from .db import close_db, get_db, init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["DATABASE"] = config.DATABASE
app.teardown_appcontext(close_db)
with app.app_context():
    init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.context_processor
def inject_globals():
    count = 0
    if "user_id" in session:
        row = get_db().execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = ?", (session["user_id"],)
        ).fetchone()
        count = row[0]
    return {"cart_count": count, "user_name": session.get("user_name")}


@app.route("/")
def index():
    db = get_db()
    featured = db.execute("SELECT * FROM books WHERE id IN (SELECT MIN(id) FROM books GROUP BY category) ORDER BY id LIMIT 4").fetchall()
    categories = db.execute("SELECT category, COUNT(*) AS n FROM books GROUP BY category ORDER BY category").fetchall()
    return render_template("index.html", featured=featured, categories=categories)


@app.route("/books")
def catalog():
    category = request.args.get("category")
    db = get_db()
    if category:
        books = db.execute("SELECT * FROM books WHERE category = ? ORDER BY title", (category,)).fetchall()
    else:
        books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    categories = db.execute("SELECT DISTINCT category FROM books ORDER BY category").fetchall()
    return render_template("catalog.html", books=books, categories=categories, selected=category, query=None)


@app.route("/search")
def search():
    q = request.args.get("q", "")
    db = get_db()
    sql = "SELECT * FROM books WHERE title LIKE '%" + q + "%' OR author LIKE '%" + q + "%' ORDER BY title"
    books = db.execute(sql).fetchall()
    categories = db.execute("SELECT DISTINCT category FROM books ORDER BY category").fetchall()
    return render_template("catalog.html", books=books, categories=categories, selected=None, query=q)


COVER_STYLES = {
    "Fiction": ("#6b1f33", "#d6603f", "circles"),
    "History": ("#4a3217", "#c79a45", "arches"),
    "Self-development": ("#14503f", "#57b88c", "bars"),
    "Technology": ("#12234a", "#4b86e8", "grid"),
    "Science": ("#2f2260", "#9a78e6", "orbits"),
}


@app.route("/cover/<int:book_id>.svg")
def cover(book_id):
    row = get_db().execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        abort(404)
    dark, light, pattern = COVER_STYLES.get(row["category"], ("#2b3a42", "#6c8794", "circles"))
    lines = textwrap.wrap(row["title"], 14)[:4]
    longest = max(len(line) for line in lines)
    size = 28 if len(lines) >= 3 else (32 if longest > 11 else 38)
    svg = render_template(
        "cover.svg", dark=dark, light=light, pattern=pattern, lines=lines, size=size,
        author=row["author"], category=row["category"],
    )
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "max-age=3600"})


@app.route("/books/<int:book_id>")
def book(book_id):
    row = get_db().execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        abort(404)
    return render_template("book.html", book=row)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session["user_id"], session["user_name"] = user["id"], user["name"]
            if request.args.get("next") == "/cart":  # the only page that sends people to log in
                return redirect(url_for("cart"))
            return redirect(url_for("index"))
        error = "Incorrect email or password."
    return render_template("login.html", error=error), (401 if error else 200)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/cart")
@login_required
def cart():
    items = get_db().execute(
        "SELECT b.id, b.title, b.author, b.price, c.quantity FROM cart_items c "
        "JOIN books b ON b.id = c.book_id WHERE c.user_id = ? ORDER BY b.title",
        (session["user_id"],),
    ).fetchall()
    total = sum(i["price"] * i["quantity"] for i in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required
def add_to_cart(book_id):
    db = get_db()
    if db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone() is None:
        abort(404)
    db.execute(
        "INSERT INTO cart_items (user_id, book_id, quantity) VALUES (?, ?, 1) "
        "ON CONFLICT(user_id, book_id) DO UPDATE SET quantity = quantity + 1",
        (session["user_id"], book_id),
    )
    db.commit()
    flash("Added to your cart.")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:book_id>", methods=["POST"])
@login_required
def remove_from_cart(book_id):
    db = get_db()
    db.execute("DELETE FROM cart_items WHERE user_id = ? AND book_id = ?", (session["user_id"], book_id))
    db.commit()
    return redirect(url_for("cart"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=True)
