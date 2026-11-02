import os
import uuid
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import csrf, db, login, migrate


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", "postgresql+psycopg://hamro:hamro@localhost:5432/hamro"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MEDIA_ROOT=os.getenv("MEDIA_ROOT", str(Path(app.instance_path) / "media")),
        MAX_CONTENT_LENGTH=102 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        WTF_CSRF_TIME_LIMIT=12 * 60 * 60,
        GEOCODER_URL=os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search"),
        GEOCODER_AGENT=os.getenv("GEOCODER_AGENT", ""),
        TILE_URL=os.getenv("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
    )
    if config:
        app.config.update(config)
    if (
        not app.config["SECRET_KEY"]
        or len(app.config["SECRET_KEY"]) < 32
        or app.config["SECRET_KEY"].startswith("replace-with")
    ):
        raise RuntimeError("Set SECRET_KEY to at least 32 random characters")
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
        raise RuntimeError("PostgreSQL/PostGIS is required; SQLite is not supported")
    if os.getenv("TRUST_PROXY", "0") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    login.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    login.login_view = "web.login_view"
    from .models import User

    @login.user_loader
    def load_user(uid):
        try:
            return db.session.get(User, uuid.UUID(uid))
        except ValueError:
            return None

    @app.context_processor
    def globals_():
        return {"mutation_token": lambda: str(uuid.uuid4()), "tile_url": app.config["TILE_URL"]}

    @app.template_filter("npr")
    def npr(value):
        return "Rs. " + format(value, ",.2f") if value is not None else "Rate unavailable"

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self'; media-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        if app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def invalid(exc):
        db.session.rollback()
        return render_template("error.html", code=400, message=str(exc)), 400

    @app.errorhandler(IntegrityError)
    def conflict(exc):
        db.session.rollback()
        return render_template(
            "error.html",
            code=409,
            message="This conflicts with an existing record. Check your details and reload.",
        ), 409

    @app.errorhandler(HTTPException)
    def http_error(exc):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return jsonify(error=exc.description), exc.code
        return render_template("error.html", code=exc.code, message=exc.description), exc.code

    from .admin import admin
    from .cli import register_cli
    from .merchant import merchant
    from .routes import web

    app.register_blueprint(web)
    app.register_blueprint(merchant)
    app.register_blueprint(admin)
    register_cli(app)
    return app
