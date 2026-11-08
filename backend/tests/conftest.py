import os

# Tests must never read the developer's real .env (it holds real keys), so the
# loader is switched off before anything from `app` is imported.
os.environ["YAQIDH_NO_DOTENV"] = "1"
