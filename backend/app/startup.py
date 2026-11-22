"""The summary the backend prints when it starts: which settings file it read and what is switched on.

Most "it works on one laptop but not on mine" problems are a missing or misplaced backend/.env, or
MySQL not running. This report says so in plain words as soon as the backend starts.
"""
from pathlib import Path

import sqlalchemy as sa
from flask import Flask

BACKEND_DIR = Path(__file__).resolve().parent.parent


def report_rows(app: Flask, settings_file: Path | None) -> list[tuple[str, str]]:
    """(label, text) pairs for the startup report. Also gets the database ready, like the first request would."""
    cfg = app.config
    with app.app_context():
        return [
            ("Settings file", _settings_status(settings_file)),
            ("Database", _database_status(app)),
            ("Sign-in codes", _email_status(cfg)),
            ("AI analysis", _ai_status(cfg)),
            ("Reading scans", _ocr_status()),
        ]


def print_report(app: Flask, settings_file: Path | None) -> None:
    rows = report_rows(app, settings_file)
    width = max(len(label) for label, _ in rows)
    lines = ["", "=" * 78, " FileAI backend - settings in use"]
    for label, text in rows:
        first, *more = text.split("\n")
        lines.append(f"  {label.ljust(width)} : {first}")
        lines.extend(f"  {' ' * width}   {extra}" for extra in more)
    lines += ["=" * 78, ""]
    print("\n".join(lines), flush=True)


def _settings_status(settings_file: Path | None) -> str:
    if settings_file is None:
        return ("none found, so the defaults are used\n"
                "-> to change them: copy backend/.env.example to backend/.env and edit it")
    if settings_file == BACKEND_DIR / ".env":
        return "backend/.env"
    return f"{settings_file}\n-> it was read, but please rename/move it to backend/.env"


def _database_status(app: Flask) -> str:
    from .upgrade import prepare_database

    url = sa.engine.make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    where = url.get_backend_name()
    if url.host:
        where += f" {url.host}:{url.port or 3306}"
    where += f"/{url.database or ''}"
    try:
        prepare_database()
    except Exception as exc:
        reason = str(getattr(exc, "orig", None) or exc).splitlines()[0][:150]
        return (f"{where} - NOT WORKING: {reason}\n"
                "-> start MySQL (Windows: Laragon/XAMPP, macOS: `brew services start mysql`, XAMPP or MAMP)\n"
                "-> if your MySQL user has a password, put it in DATABASE_URL in backend/.env")
    app.extensions["fileai_db_ready"] = True
    return f"{where} - ready"


def _email_status(cfg) -> str:
    if not cfg["TWO_FACTOR_ENABLED"]:
        return "off (TWO_FACTOR_ENABLED=false) - sign in with email and password only"
    if cfg["SMTP_HOST"]:
        return f"emailed through {cfg['SMTP_HOST']}:{cfg['SMTP_PORT']}"
    if cfg["EMAIL_DEMO_MODE"]:
        return ("DEMO MODE - no email server set up, so each code is shown on the sign-in screen\n"
                "and printed in this window. To email real codes, fill in SMTP_* in backend/.env")
    return ("BLOCKED - no SMTP_HOST and EMAIL_DEMO_MODE=false, so nobody can sign up or sign in\n"
            "-> fill in the SMTP_* settings in backend/.env, or set EMAIL_DEMO_MODE=true")


def _ai_status(cfg) -> str:
    from .services.ai import provider_info

    if provider_info()["ai_provider"] == "openai":
        return f"OpenAI {cfg['OPENAI_MODEL']}"
    if cfg["AI_PROVIDER"] == "openai" and cfg["OPENAI_API_KEY"]:
        return "local model - the OpenAI client could not start (see the error above)"
    if cfg["AI_PROVIDER"] == "local" and cfg["OPENAI_API_KEY"]:
        return "local model (AI_PROVIDER=local) - remove that line from backend/.env to use OpenAI"
    return "local model - add OPENAI_API_KEY to backend/.env to use GPT"


def _ocr_status() -> str:
    from .services.extraction import ocr_provider

    provider = ocr_provider()
    if provider == "tesseract":
        return "Tesseract OCR"
    if provider == "openai":
        return "GPT vision (OpenAI)"
    return "not available - add OPENAI_API_KEY to backend/.env (or install Tesseract)"
