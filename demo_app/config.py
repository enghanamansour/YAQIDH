import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.environ.get("MAKTABTI_DB", str(BASE_DIR / "maktabti.db"))

# Used to sign the session cookie and to call the shipping provider.
SECRET_KEY = "maktabti-dev-secret"
SHIPPING_API_TOKEN = "ghp_Zq8RtLmN3vXcP5wYb7KdJh2FsA9eUo4GiT1x"  # TODO move to env before launch
