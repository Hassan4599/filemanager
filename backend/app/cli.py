"""Command-line tools: `flask --app run.py <command>`."""
import click
from flask import Flask

from .extensions import db


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    @click.option("--drop", is_flag=True, help="Drop all tables first (deletes all data!).")
    def init_db(drop: bool):
        """Create the database (MySQL) and all tables, or upgrade an older database."""
        from .upgrade import create_mysql_database_if_missing, upgrade_database

        create_mysql_database_if_missing()
        if drop:
            click.confirm("This deletes ALL data. Continue?", abort=True)
            db.drop_all()
        for change in upgrade_database():
            click.echo(f"Upgraded: {change}")
        click.echo("Database tables are ready.")

    @app.cli.command("seed-demo")
    @click.option("--email", default="demo@fileai.test", show_default=True)
    @click.option("--password", default="Demo@12345", show_default=True)
    def seed_demo(email: str, password: str):
        """Create a demo account with sample documents processed by the AI pipeline."""
        from .demo import seed

        user, count = seed(email, password)
        click.echo(f"Demo account ready: {user.email} / {password}  ({count} documents added)")

    @app.cli.command("send-test-email")
    @click.argument("to")
    def send_test_email(to: str):
        """Send a sample verification-code email to TO, to check the SMTP settings in .env."""
        from email.message import EmailMessage

        from .services.mailer import email_configured, send_message

        if not email_configured():
            raise click.ClickException("SMTP_HOST is empty in .env, so the app is in demo mode (no emails).")
        cfg = app.config
        mode = "SSL" if cfg["SMTP_USE_SSL"] else ("STARTTLS" if cfg["SMTP_USE_TLS"] else "plain")
        click.echo(f"Sending through {cfg['SMTP_HOST']}:{cfg['SMTP_PORT']} ({mode}) as {cfg['MAIL_FROM']} ...")
        message = EmailMessage()
        message["Subject"] = "FileAI test email"
        message["From"] = cfg["MAIL_FROM"]
        message["To"] = to
        message.set_content("This is a test from FileAI. The email settings work, so sign-in codes will arrive.")
        try:
            send_message(message)
        except Exception as exc:
            raise click.ClickException(f"Could not send: {exc}")
        click.echo(f"Sent. Check the inbox (and spam folder) of {to}.")

    @app.cli.command("reindex")
    def reindex():
        """Recompute every embedding (run after changing EMBEDDING_PROVIDER)."""
        from .models import File
        from .services.index import clear_cache
        from .services.pipeline import refresh_embedding

        files = File.query.filter(File.status.in_(("AWAITING_REVIEW", "STORED"))).all()
        with click.progressbar(files, label="Re-indexing") as bar:
            for file in bar:
                if file.meta is not None:
                    refresh_embedding(file)
        db.session.commit()
        clear_cache()
        click.echo(f"Re-indexed {len(files)} documents.")

