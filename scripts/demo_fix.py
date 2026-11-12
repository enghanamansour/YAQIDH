"""Plays the developer in the demo: fixes the planted problems in demo_app the way a person would.

    python scripts/demo_fix.py qa         fixes the three QA problems (SQL injection in search, debug page leaking errors, session that never expires)
    python scripts/demo_fix.py security   fixes the security problems (secrets in code, old libraries, missing CSRF token)
    python scripts/demo_fix.py reset      puts demo_app back as it was (git checkout), so the demo can run again

Run it from the repository root. It only edits files under demo_app/.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "demo_app"


def sub(name: str, old: str, new: str) -> None:
    path = APP / name
    text = path.read_text(encoding="utf-8")
    if new in text:  # already fixed: running a fix twice is harmless
        return
    if old not in text:
        raise SystemExit(f"cannot fix {name}: the expected code is not there (run 'reset' first?)")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")


def fix_qa() -> None:
    sub("app.py", """    sql = "SELECT * FROM books WHERE title LIKE '%" + q + "%' OR author LIKE '%" + q + "%' ORDER BY title"
    books = db.execute(sql).fetchall()""", """    like = "%" + q + "%"
    books = db.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ? ORDER BY title", (like, like)).fetchall()""")
    sub("app.py", "debug=True", "debug=False")
    # a signed-in session ends after an hour
    sub("app.py", "import textwrap\n", "import textwrap\nfrom datetime import timedelta\n")
    sub("app.py", 'app.config["DATABASE"] = config.DATABASE\n',
        'app.config["DATABASE"] = config.DATABASE\napp.permanent_session_lifetime = timedelta(hours=1)  # a signed-in session ends after an hour\n')
    sub("app.py", '            session["user_id"], session["user_name"] = user["id"], user["name"]\n',
        '            session.permanent = True\n            session["user_id"], session["user_name"] = user["id"], user["name"]\n')


def fix_security() -> None:
    shutil.rmtree(APP / "__pycache__", ignore_errors=True)  # old compiled code still holds the secrets
    sub("config.py", 'SECRET_KEY = "maktabti-dev-secret"', 'SECRET_KEY = os.environ.get("MAKTABTI_SECRET_KEY") or os.urandom(32).hex()')
    sub("config.py", 'SHIPPING_API_TOKEN = "ghp_Zq8RtLmN3vXcP5wYb7KdJh2FsA9eUo4GiT1x"  # TODO move to env before launch',
        'SHIPPING_API_TOKEN = os.environ.get("SHIPPING_API_TOKEN", "")')
    (APP / "requirements.txt").write_text("flask==3.1.3\njinja2==3.1.6\nrequests==2.33.0\n", encoding="utf-8")
    # CSRF: a token in the session, checked on every POST, and a hidden field in every POST form
    sub("app.py", "import os\n", "import hmac\nimport os\nimport secrets\n")
    sub("app.py", "@app.after_request\ndef security_headers", '''@app.before_request
def csrf_protect():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    if request.method == "POST" and not hmac.compare_digest(request.form.get("csrf_token", ""), session["csrf_token"]):
        abort(400)


@app.after_request
def security_headers''')
    field = '<input type="hidden" name="csrf_token" value="{{ session.csrf_token }}">'
    for page in (APP / "templates").glob("*.html"):
        text = page.read_text(encoding="utf-8")
        page.write_text(re.sub(r'(<form[^>]*method="post"[^>]*>)', lambda m: m.group(1) + field, text), encoding="utf-8", newline="")


def main() -> None:
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "qa":
        fix_qa()
    elif what == "security":
        fix_security()
    elif what == "reset":
        subprocess.run(["git", "checkout", "--", "demo_app"], cwd=ROOT, check=True)
    else:
        raise SystemExit(__doc__)
    print("done:", what)


if __name__ == "__main__":
    main()
