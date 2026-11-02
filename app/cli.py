import getpass
import time

import click
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Banner, Category, Plan, Rate, Unit, User
from .services.core import phone
from .services.media import process_one


def register_cli(app):
    @app.cli.command("seed")
    def seed():
        """Idempotent configuration seed; no fake merchants, products or credentials."""
        for name, products, reels, hours in [
            ("Free", 20, 0, 0),
            ("Standard", 80, 1, 20),
            ("Premium", 300, 5, 50),
        ]:
            if not db.session.get(Plan, name):
                db.session.add(Plan(name=name, products=products, reels=reels, hours=hours))
        for name in ["Necklaces", "Earrings", "Rings", "Bangles", "Bracelets"]:
            if not db.session.scalar(select(Category).where(Category.name == name)):
                db.session.add(Category(name=name))
        # Initial rates must be supplied by the operator, never presented as live market data.
        for metal in ("Gold", "Silver"):
            if not db.session.get(Rate, metal):
                value = click.prompt(f"Initial pure {metal} rate NPR/gram", type=str)
                from .services.core import decimal

                db.session.add(Rate(metal=metal, value=decimal(value, ".0001", places=4)))
        for name, symbol, grams in [("Tola", "tola", "11.6638"), ("Aana", "aana", ".7289875")]:
            if not db.session.scalar(select(Unit).where(Unit.symbol == symbol)):
                db.session.add(Unit(name=name, symbol=symbol, grams=grams))
        titles = [
            ("THE BRIDAL EDIT", "Tradition, beautifully reimagined.", "📿"),
            ("SILVER STORIES", "Everyday pieces. Lasting memories.", "💍"),
            ("HERITAGE CRAFT", "Jewellery with a story to tell.", "✨"),
            ("MODERN MINIMAL", "A little luxury, every day.", "✦"),
            ("FESTIVE FAVOURITES", "Made for the moments that matter.", "⭕"),
            ("DISCOVER LOCAL", "Find exceptional jewellers near you.", "⌖"),
        ]
        for i, (eyebrow, title, art) in enumerate(titles, 1):
            if not db.session.scalar(select(Banner).where(Banner.position == i)):
                db.session.add(
                    Banner(
                        position=i,
                        eyebrow=eyebrow,
                        title=title,
                        art=art,
                        href="/stores" if i == 6 else "/#catalogue",
                    )
                )
        db.session.commit()
        click.echo("Configuration seeded. No demo accounts were created.")

    @app.cli.command("create-admin")
    @click.option("--phone-number", prompt=True)
    @click.option("--name", prompt=True)
    def create_admin(phone_number, name):
        password = getpass.getpass("Password (12+ characters): ")
        if len(password) < 12 or len(password) > 128:
            raise click.ClickException("Use 12–128 characters")
        if password != getpass.getpass("Confirm password: "):
            raise click.ClickException("Passwords differ")
        db.session.add(
            User(
                phone=phone(phone_number),
                name=name,
                password_hash=generate_password_hash(password),
                role="admin",
            )
        )
        db.session.commit()
        click.echo("Administrator created.")

    @app.cli.command("worker")
    @click.option("--once", is_flag=True)
    def worker(once):
        while True:
            try:
                worked = process_one()
            except Exception:
                db.session.rollback()
                app.logger.exception("Worker iteration failed")
                worked = False
            if once:
                break
            if not worked:
                time.sleep(2)

    @app.cli.command("cleanup")
    def cleanup():
        """Delete unreferenced local media older than 24h, and expired throttles/tokens."""
        from datetime import timedelta

        from sqlalchemy import delete

        from .models import Media, Mutation, Throttle, now
        from .services.media import root

        known = set()
        for m in db.session.scalars(select(Media)):
            known.update(x for x in [m.source, m.output, m.thumbnail, *m.variants.values()] if x)
        cutoff = time.time() - 86400
        count = 0
        for p in root().iterdir():
            if p.is_file() and p.name not in known and p.stat().st_mtime < cutoff:
                p.unlink()
                count += 1
        db.session.execute(delete(Throttle).where(Throttle.expires < now() - timedelta(days=1)))
        db.session.execute(delete(Mutation).where(Mutation.created_at < now() - timedelta(days=30)))
        db.session.commit()
        click.echo(f"Removed {count} orphaned media files.")
