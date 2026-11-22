"""A fresh copy of the project (git clone, no backend/.env) must work straight away."""
import os
import subprocess
import sys
from pathlib import Path

from app import create_app
from app.config import TestConfig
from app.startup import report_rows

BACKEND_DIR = Path(__file__).resolve().parent.parent
SETTINGS = ("EMAIL_DEMO_MODE", "SMTP_HOST", "AI_PROVIDER", "OPENAI_API_KEY", "TWO_FACTOR_ENABLED")
NEW_USER = {"name": "New Student", "email": "student@example.com", "password": "Passw0rd!"}


def fresh_config(**env) -> dict:
    """Read Config in a new Python process with none of our settings in the environment except `env`."""
    clean = {name: value for name, value in os.environ.items() if name not in SETTINGS}
    clean.update(env)
    code = "from app.config import Config as C; print(C.EMAIL_DEMO_MODE, C.AI_PROVIDER)"
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_DIR, env=clean,
                         capture_output=True, text=True, check=True)
    demo, provider = out.stdout.split()
    return {"EMAIL_DEMO_MODE": demo == "True", "AI_PROVIDER": provider}


def test_fresh_copy_shows_codes_on_screen_and_uses_the_local_ai():
    assert fresh_config() == {"EMAIL_DEMO_MODE": True, "AI_PROVIDER": "local"}


def test_an_openai_key_alone_switches_gpt_on():
    assert fresh_config(OPENAI_API_KEY="sk-test")["AI_PROVIDER"] == "openai"
    assert fresh_config(OPENAI_API_KEY="sk-test", AI_PROVIDER="")["AI_PROVIDER"] == "openai"
    assert fresh_config(OPENAI_API_KEY="sk-test", AI_PROVIDER="local")["AI_PROVIDER"] == "local"


def test_sign_up_and_sign_in_work_without_an_email_server(client):
    client.application.config.update(TWO_FACTOR_ENABLED=True, SMTP_HOST="", EMAIL_DEMO_MODE=True)

    res = client.post("/api/auth/register", json=NEW_USER)
    assert res.status_code == 202
    res = client.post("/api/auth/register/verify", json={"email": NEW_USER["email"], "code": res.get_json()["demo_code"]})
    assert res.status_code == 201

    res = client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]})
    assert res.status_code == 202
    res = client.post("/api/auth/login/verify", json={"email": NEW_USER["email"], "code": res.get_json()["demo_code"]})
    assert res.status_code == 200 and res.get_json()["access_token"]


def test_database_problem_gives_a_clear_message_not_something_went_wrong(tmp_path):
    broken_db = f"sqlite:///{(tmp_path / 'no-such-folder' / 'app.db').as_posix()}"
    app = create_app(TestConfig, LOCAL_STORAGE_DIR=str(tmp_path / "uploads"), SQLALCHEMY_DATABASE_URI=broken_db)
    client = app.test_client()
    for res in (client.post("/api/auth/register", json=NEW_USER),
                client.post("/api/auth/login", json={"email": NEW_USER["email"], "password": NEW_USER["password"]})):
        assert res.status_code == 503
        assert res.get_json()["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert "MySQL" in res.get_json()["error"]["message"]

    rows = dict(report_rows(app, None))
    assert "NOT WORKING" in rows["Database"] and "start MySQL" in rows["Database"]


def test_startup_report_says_what_is_set_up(app, monkeypatch):
    from app.services import extraction

    monkeypatch.setattr(extraction, "tesseract_available", lambda: False)
    rows = dict(report_rows(app, None))
    assert "none found" in rows["Settings file"]
    assert rows["Database"].endswith("- ready")
    assert "add OPENAI_API_KEY" in rows["AI analysis"]
    assert "not available" in rows["Reading scans"]

    app.config.update(TWO_FACTOR_ENABLED=True, SMTP_HOST="", EMAIL_DEMO_MODE=True)
    assert dict(report_rows(app, None))["Sign-in codes"].startswith("DEMO MODE")
    app.config.update(EMAIL_DEMO_MODE=False)
    assert dict(report_rows(app, None))["Sign-in codes"].startswith("BLOCKED")
    app.config.update(SMTP_HOST="smtp.example.com", SMTP_PORT=465)
    assert dict(report_rows(app, None))["Sign-in codes"] == "emailed through smtp.example.com:465"
