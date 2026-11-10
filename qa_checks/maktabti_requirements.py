"""Checks for the demo requirements (see config/requirements.yaml).

Same rule as the security checks: a check passes when the requirement holds and fails (AssertionError) when it does not.
A feature the demo shop does not have yet fails honestly: that is a gap the QA reviewer must see.
"""

import re
import time
from pathlib import Path
from urllib.parse import quote

from src.tools.qa.checks import Check

APP_DIR = Path(__file__).resolve().parent.parent / "demo_app"
EMAIL, PASSWORD = "sara@example.com", "books2024"  # the demo shop's seeded test account


def _login(page, base_url, password=PASSWORD):
    page.goto(f"{base_url}/login")
    page.fill("input[name=email]", EMAIL)
    page.fill("input[name=password]", password)
    page.click("main form button[type=submit]")


def passwords_are_stored_hashed(page, base_url):
    from demo_app import db
    assert "password_hash" in db.SCHEMA, "the users table has no password_hash column"
    assert "generate_password_hash" in (APP_DIR / "db.py").read_text(), "seeded passwords are not hashed"


def session_expires_after_inactivity(page, base_url):
    _login(page, base_url)
    session = [c for c in page.context.cookies() if c["name"] == "session"]
    assert session, "no session cookie after login"
    expires = session[0]["expires"]
    assert expires != -1 and expires - time.time() <= 8 * 3600, "the session cookie has no expiry: the session never times out"


def search_output_is_escaped(page, base_url):
    payload = "<script>window.__xss=1</script>"
    page.goto(f"{base_url}/search?q={quote(payload)}")
    assert page.evaluate("window.__xss") != 1, "a script typed in the search box was executed"


def cart_add_and_quantity_work(page, base_url):
    _login(page, base_url)
    for _ in range(2):  # like a person: open the book and press the button (so a CSRF token in the form is sent too)
        page.goto(f"{base_url}/books/1")
        page.click("[data-testid=add-to-cart]")
    page.goto(f"{base_url}/cart")
    quantity = page.locator("[data-testid=cart-table] tbody tr td:nth-child(2)").first.inner_text().strip()
    assert quantity == "2", f"adding the same book twice gave quantity {quantity!r}, expected 2"


def search_finds_books_by_title_and_author(page, base_url):
    for term in ("Alchemist", "Hosseini"):
        page.goto(f"{base_url}/search?q={term}")
        assert page.locator("[data-testid=book-card]").count() >= 1, f"searching for {term!r} found nothing"


def card_data_is_not_stored(page, base_url):
    from demo_app import db
    found = re.findall(r"\b(card_number|cvv|cvc|pan)\b", db.SCHEMA, re.I)
    assert not found, f"the database stores card data: {', '.join(found)}"


def other_users_orders_are_not_visible(page, base_url):
    response = page.goto(f"{base_url}/orders/1")
    assert response.status != 200 or "/login" in page.url, "an anonymous visitor can open order 1"


def upload_accepts_images_only(page, base_url):
    response = page.request.post(f"{base_url}/upload", multipart={"file": {"name": "x.txt", "mimeType": "text/plain", "buffer": b"not an image"}})
    assert not 200 <= response.status < 300, f"a text file was accepted by /upload (HTTP {response.status})"


def home_page_loads_fast(page, base_url):
    start = time.monotonic()
    page.goto(base_url)
    elapsed = time.monotonic() - start
    assert elapsed < 3, f"the home page took {elapsed:.1f}s to load"


REQUIREMENT_CHECKS = [
    Check("passwords_are_stored_hashed", passwords_are_stored_hashed, "R-07: passwords must be stored hashed"),
    Check("session_expires_after_inactivity", session_expires_after_inactivity, "R-09: sessions must expire"),
    Check("search_output_is_escaped", search_output_is_escaped, "R-10: search must not run scripts (XSS)"),
    Check("cart_add_and_quantity_work", cart_add_and_quantity_work, "R-13: the cart adds books and counts the quantity"),
    Check("search_finds_books_by_title_and_author", search_finds_books_by_title_and_author, "R-14: search by title or author works"),
    Check("card_data_is_not_stored", card_data_is_not_stored, "R-16: card data must not be stored"),
    Check("other_users_orders_are_not_visible", other_users_orders_are_not_visible, "R-17: orders are private"),
    Check("upload_accepts_images_only", upload_accepts_images_only, "R-18: uploads accept images only"),
    Check("home_page_loads_fast", home_page_loads_fast, "R-20: the home page loads in under 3 seconds"),
]
