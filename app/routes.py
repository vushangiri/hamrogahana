import uuid
from datetime import timedelta

import requests
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import (
    Banner,
    Category,
    Delivery,
    Feature,
    GeoCache,
    Media,
    Product,
    Rate,
    Store,
    Unit,
    User,
    now,
)
from .security import throttle
from .services.catalogue import catalogue, public_conditions
from .services.core import audit, breakdown, coordinates, decimal, eligible, phone, text
from .services.media import path_for, upload

web = Blueprint("web", __name__)


def product_context(p):
    rate = db.session.get(Rate, p.metal)
    return {
        "product": p,
        "cost": breakdown(rate.value, p.purity, p.weight, p.store.surplus, p.making, p.fixed),
        "units": db.session.scalars(select(Unit).where(Unit.active)).all(),
        "rate": rate,
    }


@web.get("/")
def discover():
    rows, more, page = catalogue(request.args)
    features = db.session.scalars(
        select(Feature)
        .join(Product)
        .join(Store)
        .where(
            *public_conditions(),
            Feature.status == "scheduled",
            Feature.start <= now(),
            Feature.end > now(),
        )
        .options(joinedload(Feature.product).joinedload(Product.store))
    ).all()
    current_rates = {rate.metal: rate for rate in db.session.scalars(select(Rate)).all()}
    spotlight = []
    for f in features:
        p = f.product
        r = current_rates[p.metal]
        spotlight.append(
            (
                p,
                breakdown(r.value, p.purity, p.weight, p.store.surplus, p.making, p.fixed)["total"],
                None,
            )
        )
        stmt = insert(Delivery).values(feature_id=f.id, day=now().date(), impressions=1)
        db.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["feature_id", "day"],
                set_={"impressions": Delivery.impressions + 1},
            )
        )
    db.session.commit()
    ctx = dict(
        rows=rows,
        more=more,
        page=page,
        spotlight=spotlight,
        rates=list(current_rates.values()),
        banners=db.session.scalars(
            select(Banner).where(Banner.active).order_by(Banner.position)
        ).all(),
        categories=db.session.scalars(select(Category).order_by(Category.name)).all(),
        active="discover",
    )
    return render_template(
        "catalogue.html" if request.headers.get("HX-Request") else "discover.html", **ctx
    )


@web.get("/products/<uuid:pid>")
def product(pid):
    p = db.session.scalar(
        select(Product)
        .join(Store)
        .where(Product.id == pid, *public_conditions())
        .options(joinedload(Product.store))
    )
    if not p:
        abort(404)
    return render_template("product.html", **product_context(p))


@web.get("/stores")
def stores():
    lat, lon = coordinates(request.args.get("lat", "27.704"), request.args.get("lon", "85.311"))
    point = func.ST_GeogFromText(f"SRID=4326;POINT({lon} {lat})")
    radius = decimal(request.args.get("radius", "50"), ".1", "1000")
    rows = db.session.execute(
        select(Store, func.ST_Distance(Store.location, point))
        .where(
            Store.active,
            Store.verification == "verified",
            func.ST_DWithin(Store.location, point, radius * 1000),
        )
        .order_by(func.ST_Distance(Store.location, point), Store.id)
        .limit(50)
    ).all()
    return render_template("stores.html", rows=rows, active="stores")


@web.get("/stores/<uuid:sid>")
def store(sid):
    s = db.get_or_404(Store, sid)
    if not eligible(s):
        abort(404)
    rows, more, page = catalogue({"sort": "new", **request.args}, store_id=s.id)
    return render_template(
        "store.html", store=s, rows=rows, more=more, page=page, active="stores"
    )


@web.get("/saved")
def saved():
    rows, more, page = catalogue(
        {**request.args, "ids": request.args.get("ids", str(uuid.UUID(int=0))), "radius": "1000"}
    )
    return render_template("saved.html", rows=rows, more=more, page=page, active="saved")


@web.get("/reels")
def reels():
    page = max(1, min(int(request.args.get("page", 1)), 10000))
    rows = db.session.scalars(
        select(Media)
        .join(Product)
        .join(Store)
        .where(*public_conditions(), Media.kind == "reel", Media.status == "ready")
        .options(joinedload(Media.product).joinedload(Product.store))
        .order_by(Media.created_at.desc(), Media.id)
        .limit(6)
        .offset((page - 1) * 5)
    ).all()
    return render_template(
        "reels.html", reels=rows[:5], more=len(rows) > 5, page=page, active="reels"
    )


@web.get("/location")
def location():
    return render_template("location.html")


@web.get("/appearance")
def appearance():
    return render_template("appearance.html")


@web.route("/login", methods=["GET", "POST"])
@web.route("/admin/login", methods=["GET", "POST"])
def login_view():
    is_admin = request.path.startswith("/admin")
    if request.method == "POST":
        throttle("login-ip:" + request.remote_addr, 30, 900)
        number = phone(request.form.get("phone", ""))
        throttle("login-user:" + number, 10, 900)
        user = db.session.scalar(select(User).where(User.phone == number))
        # Always perform a password check, including unknown accounts.
        fallback = current_app.config.get("DUMMY_HASH")
        if not fallback:
            fallback = generate_password_hash("random-unused-password")
            current_app.config["DUMMY_HASH"] = fallback
        valid = check_password_hash(
            user.password_hash if user else fallback, request.form.get("password", "")
        )
        if not valid or not user or (user.role == "admin") != is_admin:
            flash("Invalid credentials for this workspace.", "error")
            return render_template("login.html", is_admin=is_admin), 401
        session.clear()
        login_user(user)
        session.permanent = True
        audit("auth.login", user.id)
        db.session.commit()
        return redirect("/admin" if is_admin else "/merchant")
    return render_template("login.html", is_admin=is_admin)


@web.post("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect("/")


@web.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        throttle("register:" + request.remote_addr, 5, 3600)
        password = request.form.get("password", "")
        if not 12 <= len(password) <= 128:
            raise ValueError("Use a password of 12–128 characters")
        lat, lon = coordinates(request.form.get("latitude"), request.form.get("longitude"))
        u = User(
            phone=phone(request.form.get("phone", "")),
            name=text(request.form.get("owner_name"), 120),
            email=text(request.form.get("email"), 254, False) or None,
            password_hash=generate_password_hash(password),
        )
        db.session.add(u)
        db.session.flush()
        s = Store(
            owner_id=u.id,
            name=text(request.form.get("name")),
            phone=phone(request.form.get("store_phone", "")),
            address=text(request.form.get("address"), 500),
            latitude=lat,
            longitude=lon,
            location=f"SRID=4326;POINT({lon} {lat})",
            surplus=decimal(request.form.get("surplus"), places=4),
        )
        db.session.add(s)
        db.session.flush()
        if request.files.get("document") and request.files["document"].filename:
            upload(request.files["document"], s, "document")
        audit("store.registered", s.id)
        db.session.commit()
        session.clear()
        login_user(u)
        return redirect("/merchant")
    return render_template("register.html")


def accessible_media(mid):
    m = db.get_or_404(Media, mid)
    public = (
        m.kind in ("image", "reel")
        and m.status == "ready"
        and m.product
        and m.product.status == "published"
        and eligible(m.product.store)
    )
    permitted = current_user.is_authenticated and (
        current_user.role == "admin"
        or db.session.get(Store, m.store_id).owner_id == current_user.id
    )
    if not public and not permitted:
        abort(404)
    return m


@web.get("/media/<uuid:mid>/preview")
def media_preview(mid):
    m = accessible_media(mid)
    if not m.output or m.output.endswith(".upload"):
        abort(404)
    return render_template("media_preview.html", media=m)


@web.get("/media/<uuid:mid>/<variant>")
def media(mid, variant):
    m = accessible_media(mid)
    key = (
        m.thumbnail
        if variant == "thumb"
        else m.variants.get(variant)
        if variant in ("320", "640", "1280")
        else m.output
        if variant == "file"
        else None
    )
    if not key:
        abort(404)
    path = path_for(key)
    response = send_from_directory(
        path.parent,
        path.name,
        conditional=True,
        as_attachment=key.endswith(".upload"),
        mimetype="application/pdf" if key.endswith(".upload") else "video/mp4"
        if key.endswith(".mp4") else "image/webp",
        download_name="evidence.pdf" if key.endswith(".upload") else None,
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@web.get("/api/geocode")
def geocode():
    throttle("geo-ip:" + request.remote_addr, 20, 60)
    q = text(request.args.get("q"), 200)
    cached = db.session.get(GeoCache, q.lower())
    if cached and cached.expires > now():
        return jsonify(cached.results)
    if not current_app.config["GEOCODER_AGENT"]:
        return jsonify(
            error="Address search is not configured. Choose a pin or enter coordinates."
        ), 503
    # One global allowance per second across all application workers; reject, never queue requests.
    throttle("geocoder-global", 1, 1)
    try:
        response = requests.get(
            current_app.config["GEOCODER_URL"],
            params={"q": q, "format": "jsonv2", "limit": 5, "countrycodes": "np"},
            headers={"User-Agent": current_app.config["GEOCODER_AGENT"]},
            timeout=8,
        )
        response.raise_for_status()
        results = [
            {"label": str(x["display_name"])[:500], "lat": x["lat"], "lon": x["lon"]}
            for x in response.json()[:5]
        ]
    except (requests.RequestException, ValueError, KeyError):
        return jsonify(error="Location search unavailable. You can still place a pin."), 503
    db.session.merge(GeoCache(query=q.lower(), results=results, expires=now() + timedelta(days=30)))
    db.session.commit()
    return jsonify(results)


@web.get("/manifest.webmanifest")
def manifest():
    return jsonify(
        name="Hamro Gahana",
        short_name="Gahana",
        id="/",
        start_url="/",
        scope="/",
        display="standalone",
        background_color="#f7f5f0",
        theme_color="#865b30",
        icons=[
            {
                "src": f"/static/icons/icon-{size}.png",
                "sizes": f"{size}x{size}",
                "type": "image/png",
                "purpose": "any maskable",
            }
            for size in (192, 512)
        ],
    )


@web.get("/sw.js")
def worker():
    return current_app.send_static_file("js/sw.js")


@web.get("/offline")
def offline():
    return render_template("offline.html")


@web.get("/health")
def health():
    db.session.execute(select(func.PostGIS_Version()))
    return jsonify(status="ok", version="1.0.0")
