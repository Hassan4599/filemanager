"""Development entry point.

    flask --app run.py init-db      # create tables
    flask --app run.py seed-demo    # optional demo account with sample documents
    flask --app run.py run --port 5000
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
# backend/.env is the right place. The other two catch the usual mistakes: the file saved in the
# project folder, or renamed to ".env.txt" by Notepad / TextEdit.
SETTINGS_FILES = (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env.txt")
settings_file = next((path for path in SETTINGS_FILES if path.is_file()), None)
if settings_file:
    load_dotenv(settings_file)

from app import create_app  # noqa: E402  (load .env before reading config)
from app.startup import print_report  # noqa: E402

app = create_app()

# When the server starts (`flask run` or `python run.py`), print what is set up and what is missing.
if __name__ == "__main__" or "run" in sys.argv[1:]:
    print_report(app, settings_file)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
