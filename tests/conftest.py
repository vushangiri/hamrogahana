import os
import uuid

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-32-characters-minimum",
            "SESSION_COOKIE_SECURE": False,
            "MEDIA_ROOT": str(tmp_path / "media"),
        }
    )


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def database(tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set: requires dedicated PostgreSQL/PostGIS database")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-32-characters-minimum",
            "SQLALCHEMY_DATABASE_URI": url,
            "WTF_CSRF_ENABLED": False,
            "SESSION_COOKIE_SECURE": False,
            "MEDIA_ROOT": str(tmp_path / "media"),
        }
    )
    from flask_migrate import upgrade
    from sqlalchemy import text

    @app.before_request
    def clear_cached_test_user():
        # Tests keep an outer app context for DB access. Real requests each get
        # a fresh context, so don't carry Flask-Login's g cache across clients.
        from flask import g

        g.pop("_login_user", None)

    # Isolated schema per test; no deletion of existing user tables.
    schema = "test_" + uuid.uuid4().hex
    with app.app_context():
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        db.session.execute(text(f"CREATE SCHEMA {schema}"))
        db.session.commit()
        from sqlalchemy import event

        @event.listens_for(db.engine, "checkout")
        def set_schema(connection, record, proxy):
            with connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {schema},public")

        db.session.remove()
        upgrade()
        from decimal import Decimal

        from werkzeug.security import generate_password_hash

        from app.models import Category, Plan, Rate, Store, User

        db.session.add_all(
            [
                Plan(name="Free", products=20, reels=0, hours=0),
                Plan(name="Standard", products=80, reels=1, hours=20),
                Plan(name="Premium", products=300, reels=5, hours=50),
                Rate(metal="Gold", value=10000),
                Rate(metal="Silver", value=100),
                Category(name="Rings"),
            ]
        )
        db.session.flush()
        admin = User(
            name="Admin",
            phone="+9779800000000",
            password_hash=generate_password_hash("testpassword123"),
            role="admin",
        )
        owner = User(
            name="Owner",
            phone="+9779800000001",
            password_hash=generate_password_hash("testpassword123"),
        )
        db.session.add_all([admin, owner])
        db.session.flush()
        store = Store(
            owner_id=owner.id,
            name="Test Jeweller",
            phone=owner.phone,
            address="Kathmandu",
            latitude=Decimal("27.704"),
            longitude=Decimal("85.311"),
            location="SRID=4326;POINT(85.311 27.704)",
            surplus=100,
            verification="verified",
            plan_name="Standard",
        )
        db.session.add(store)
        db.session.commit()
        app.config["TEST_STORE_ID"] = store.id
        app.config["TEST_OWNER_ID"] = owner.id
        app.config["TEST_ADMIN_ID"] = admin.id
        yield app
        db.session.remove()
        with db.engine.connect() as conn:
            conn.execute(text("SET search_path TO public"))
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
            conn.commit()
        event.remove(db.engine, "checkout", set_schema)
        db.engine.dispose()
