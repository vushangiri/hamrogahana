import re
from datetime import datetime, timedelta
from decimal import Decimal as D

import pytest

from app.services.core import NEPAL, breakdown, coordinates, decimal, phone, week_slices


def test_decimal_price_and_unit():
    result = breakdown(D("10000"), D(".75"), D("2"), D("100"), D("50"), D("25"))
    assert result == {
        "metal": D("15000.00"),
        "surplus": D("200.00"),
        "making": D("50.00"),
        "fixed": D("25.00"),
        "total": D("15275.00"),
    }
    assert D("2") / D(".5") == D("4")


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1e999", "hello", ""])
def test_invalid_decimal(bad):
    with pytest.raises(ValueError):
        decimal(bad)


def test_precision_rejected():
    with pytest.raises(ValueError):
        decimal("1.12345", places=4)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("9800000001", "+9779800000001"),
        ("+977 9800000001", "+9779800000001"),
        ("+61 400 123 456", "+61400123456"),
    ],
)
def test_phone_normalization(raw, expected):
    assert phone(raw) == expected


@pytest.mark.parametrize("lat,lon", [("NaN", "0"), ("91", "0"), ("0", "181"), ("", "")])
def test_coordinates_rejected(lat, lon):
    with pytest.raises(ValueError):
        coordinates(lat, lon)


def test_week_boundary_nepal():
    start = datetime(2026, 11, 8, 23, 0, tzinfo=NEPAL)
    pieces = list(week_slices(start, start + timedelta(hours=2)))
    assert len(pieces) == 2
    assert [x[2] for x in pieces] == [D(1), D(1)]
    assert all(x[0].weekday() == 0 for x in pieces)


def test_csrf_and_protected_routes(client):
    assert client.post("/logout").status_code == 400
    assert client.get("/merchant").status_code == 302
    assert client.get("/admin").status_code == 403


@pytest.mark.parametrize("route", ["/login", "/admin/login", "/register"])
@pytest.mark.parametrize("token_state", ["valid", "missing", "invalid", "expired"])
def test_auth_form_csrf(app, client, monkeypatch, route, token_state):
    from itsdangerous import TimestampSigner

    response = client.get(route)
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)
    # Isolate CSRF middleware from authentication and database writes.
    endpoint = "web.register" if route == "/register" else "web.login_view"
    monkeypatch.setitem(app.view_functions, endpoint, lambda: ("Accepted", 200))
    if token_state == "missing":
        token = ""
    elif token_state == "invalid":
        token = "invalid-token"
    elif token_state == "expired":
        # Keep the session alive so this specifically exercises token expiry.
        app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=1)
        timestamp = TimestampSigner.get_timestamp
        monkeypatch.setattr(
            TimestampSigner, "get_timestamp", lambda self: timestamp(self) + 12 * 60 * 60 + 1
        )
    response = client.post(route, data={"csrf_token": token})
    assert response.status_code == (200 if token_state == "valid" else 400)
    if token_state == "expired":
        assert "CSRF token has expired" in response.text


@pytest.mark.parametrize(
    "route",
    [
        "/login",
        "/admin/login",
        "/register",
        "/location",
        "/appearance",
        "/offline",
        "/manifest.webmanifest",
        "/sw.js",
        "/static/icons/icon-192.png",
        "/static/icons/icon-512.png",
    ],
)
def test_public_static_routes(client, route):
    response = client.get(route)
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_pwa_cache_excludes_private(client):
    sw = client.get("/sw.js").text
    assert "/merchant" not in sw and "/admin" not in sw and "/media/" not in sw
    assert client.get("/manifest.webmanifest").json["display"] == "standalone"


def test_templates_compile(app):
    for template in app.jinja_env.list_templates():
        app.jinja_env.get_template(template)


def test_database_required():
    from app import create_app

    with pytest.raises(RuntimeError):
        create_app({"SECRET_KEY": "x" * 32, "SQLALCHEMY_DATABASE_URI": "sqlite://"})


def test_catalogue_query_compiles_without_database(app, monkeypatch):
    from sqlalchemy.dialects.postgresql import dialect

    from app.extensions import db
    from app.services.catalogue import catalogue

    compiled = []

    class Result:
        def all(self):
            return []

    def execute(stmt):
        compiled.append(str(stmt.compile(dialect=dialect())))
        return Result()

    with app.app_context():
        monkeypatch.setattr(db.session, "execute", execute)
        for sort in ["near", "low", "high", "new"]:
            catalogue(
                {
                    "sort": sort,
                    "q": "gold",
                    "tags": "bridal,modern",
                    "price_min": "100",
                    "featured": "1",
                }
            )
    assert all("ST_DWithin" in q and "row_number() OVER" in q for q in compiled)
