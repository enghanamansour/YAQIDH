"""Security checks for the Maktabti demo app. Each one is a known expectation written down in advance.

The rule for a check: it must pass on a secure app and fail on a vulnerable one.
"""

from urllib.parse import quote

from src.tools.qa.checks import Check

SQLI_PAYLOAD = "zzznomatch' OR '1'='1' --"
BREAKING_INPUT = "')"  # a quote and a bracket break naive SQL
LEAK_MARKERS = ("Traceback", "sqlite3", "OperationalError", "Werkzeug Debugger")


def cart_requires_login(page, base_url):
    page.goto(f"{base_url}/cart")
    assert "/login" in page.url, f"anonymous visitor reached {page.url} instead of the login page"


def wrong_password_is_rejected(page, base_url):
    page.goto(f"{base_url}/login")
    page.fill("input[name=email]", "sara@example.com")
    page.fill("input[name=password]", "not-the-password")
    page.click("main form button[type=submit]")
    assert page.locator("[data-testid=login-error]").count() == 1, "no error shown for a wrong password"
    assert page.locator("[data-testid=greeting]").count() == 0, "wrong password still logged the user in"


def search_resists_sql_injection(page, base_url):
    page.goto(f"{base_url}/search?q={quote(SQLI_PAYLOAD)}")
    cards = page.locator("[data-testid=book-card]").count()
    assert cards == 0, f"SQL injection in the search box returned {cards} books for a title that does not exist"


def errors_do_not_leak_internals(page, base_url):
    response = page.goto(f"{base_url}/search?q={quote(BREAKING_INPUT)}")
    body = page.content()
    found = [m for m in LEAK_MARKERS if m in body]
    assert not found, f"error page (HTTP {response.status}) exposes internals: {', '.join(found)}"


def security_headers_are_set(page, base_url):
    headers = page.goto(base_url).headers
    missing = [h for h in ("x-content-type-options", "x-frame-options") if h not in headers]
    assert not missing, f"missing security headers: {', '.join(missing)}"


CHECKS = [
    Check("cart_requires_login", cart_requires_login, "The cart must not open without logging in"),
    Check("wrong_password_is_rejected", wrong_password_is_rejected, "A wrong password must not log the user in"),
    Check("search_resists_sql_injection", search_resists_sql_injection, "Search must not run user input as SQL"),
    Check("errors_do_not_leak_internals", errors_do_not_leak_internals, "Error pages must not show internals"),
    Check("security_headers_are_set", security_headers_are_set, "Basic security headers must be present"),
]
