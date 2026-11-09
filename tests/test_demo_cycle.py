import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_cycle", ROOT / "scripts" / "demo_cycle.py")
demo_cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo_cycle)


def copy_app(tmp_path):
    shutil.copytree(ROOT / "demo_app", tmp_path / "demo_app", ignore=shutil.ignore_patterns("*.db", "__pycache__"))
    return tmp_path / "demo_app"


def test_the_scripted_fixes_still_apply_to_the_demo_app(tmp_path):
    """If someone changes the demo app, the Phase 12 script must fail here, not in the middle of a presentation."""
    app = copy_app(tmp_path)
    demo_cycle.fix_sql_query(app)
    assert "LIKE ? OR author LIKE ?" in (app / "app.py").read_text()
    demo_cycle.fix_security_issues(app)
    assert "debug=True" not in (app / "app.py").read_text()
    assert "ghp_" not in (app / "config.py").read_text()
    assert "flask==3.0.3" in (app / "requirements.txt").read_text()


def test_the_fixed_query_still_works(tmp_path):
    import sqlite3

    app = copy_app(tmp_path)
    demo_cycle.fix_sql_query(app)
    assert "' OR '1'='1" not in (app / "app.py").read_text()
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE books (title TEXT, author TEXT)")
    db.execute("INSERT INTO books VALUES ('Clean Code', 'Martin')")
    q = "zzznomatch' OR '1'='1' --"
    rows = db.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ?", (f"%{q}%", f"%{q}%")).fetchall()
    assert rows == []  # the injection text is just text now
