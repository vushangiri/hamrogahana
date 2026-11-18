from datetime import datetime
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .extensions import db
from .models import Category, Feature, Media, Plan, Product, Store, Tag, Upgrade, now
from .security import once
from .services.core import (
    NEPAL,
    audit,
    cancel_feature,
    cancel_features,
    coordinates,
    decimal,
    eligible,
    locked_store,
    owner_product,
    phone,
    reel_bonus_enabled,
    reel_bonus_hours,
    reel_week,
    schedule,
    text,
)
from .services.media import upload
from .services.rates import TOLA_GRAMS

merchant = Blueprint("merchant", __name__, url_prefix="/merchant")


def my_store():
    if current_user.role != "merchant":
        abort(403)
    return db.session.execute(select(Store).where(Store.owner_id == current_user.id)).scalar_one()


@merchant.get("")
@login_required
def dashboard():
    s = my_store()
    tab = request.args.get("tab", "Overview")
    if tab not in ("Overview", "Products", "Media", "Featured", "Store", "Subscription"):
        abort(404)
    if tab == "Media":
        tab = "Products"
    page = max(1, min(10000, int(request.args.get("page", 1))))
    base = select(Product).where(Product.store_id == s.id)
    product_count = db.session.scalar(select(func.count()).select_from(base.subquery()))
    published_count = db.session.scalar(
        select(func.count()).select_from(base.where(Product.status == "published").subquery())
    )
    if tab == "Featured":
        base = base.where(Product.status == "published")
    products = db.session.scalars(
        base.order_by(Product.created_at, Product.id).limit(11).offset((page - 1) * 10)
    ).all() if tab in ("Products", "Media", "Featured") else []
    feature_page = max(1, min(10000, int(request.args.get("feature_page", 1))))
    features = db.session.scalars(
        select(Feature).where(Feature.store_id == s.id)
        .order_by(Feature.start.desc(), Feature.id)
        .limit(11).offset((feature_page - 1) * 10)
    ).all() if tab == "Featured" else []
    return render_template(
        "merchant.html",
        store=s,
        tola_grams=TOLA_GRAMS,
        products=products[:10],
        more=len(products) > 10,
        page=page,
        product_count=product_count,
        published_count=published_count,
        tab=tab,
        features=features[:10],
        feature_more=len(features) > 10,
        feature_page=feature_page,
        reel_bonus_enabled=tab == "Featured" and reel_bonus_enabled(s),
        reel_bonus=reel_bonus_hours(s, reel_week(now())) if tab == "Featured" else 0,
        upgrades=db.session.scalars(
            select(Upgrade)
            .where(Upgrade.store_id == s.id)
            .order_by(Upgrade.created_at.desc())
            .limit(50)
        ).all() if tab == "Subscription" else [],
        plans=db.session.scalars(select(Plan).order_by(Plan.products)).all() if tab == "Subscription" else [],
    )


@merchant.route("/products/new", methods=["GET", "POST"])
@merchant.route("/products/<uuid:pid>/edit", methods=["GET", "POST"])
@login_required
def edit_product(pid=None):
    s = my_store()
    p = owner_product(pid) if pid else None
    if request.method == "POST":
        once()
        s = locked_store(s.id)
        if p:
            db.session.refresh(p)
        if not s.active:
            raise ValueError("This store is suspended")
        if p and p.status in ("archived", "suspended", "excess"):
            raise ValueError("Administrator or plan restriction prevents editing")
        if not p:
            count = db.session.scalar(
                select(func.count()).select_from(Product).where(Product.store_id == s.id)
            )
            if count >= s.plan.products:
                raise ValueError("Product allowance reached")
            p = Product(store_id=s.id)
        other = request.form.get("metal") == "Other"
        p.name = text(request.form.get("description"), 5000)[:150] if other else text(request.form.get("name"))
        p.description = text(request.form.get("description"), 5000, False)
        import uuid

        category = db.session.scalar(select(Category).order_by(Category.name).limit(1)) if other else db.get_or_404(Category, uuid.UUID(request.form.get("category_id", "")))
        if category is None:
            raise ValueError("An administrator must create a product category first")
        p.category_id = category.id
        metal = request.form.get("metal")
        purity_code = request.form.get("purity")
        allowed = {
            "Gold": {"24K": Decimal(1), "22K": Decimal(22) / 24, "18K": Decimal(".75")},
            "Silver": {"999": Decimal(".999"), "925": Decimal(".925")},
        }
        if metal != "Other" and (metal not in allowed or (purity_code != "custom" and purity_code not in allowed[metal])):
            raise ValueError("Choose a valid metal and purity combination")
        p.metal = metal
        if metal == "Other":
            p.description = text(request.form.get("description"), 5000)
            p.weight_unit = "gram"
            p.purity, p.weight, p.making = Decimal(1), Decimal(1), Decimal(0)
            p.making_percentage = None
            p.fixed = decimal(request.form.get("fixed"), places=4)
        else:
            if purity_code == "custom":
                p.purity = decimal(request.form.get("custom_purity"), ".00000001", "100", 8) / 100
                purity_code = f"{(p.purity * 100).normalize():f}%"
            else:
                p.purity = allowed[metal][purity_code].quantize(Decimal(".0000000001"))
            unit = request.form.get("weight_unit", "gram")
            if unit not in ("gram", "tola"):
                raise ValueError("Choose Gram or Tola")
            p.weight_unit = unit
            p.weight = (decimal(request.form.get("weight"), ".000001", "100000", 6) * (TOLA_GRAMS if unit == "tola" else 1)).quantize(Decimal(".000001"))
            percentage = request.form.get("making_percentage", "").strip()
            if percentage:
                p.making_percentage = decimal(percentage, "0", "100", 4)
                p.making = Decimal(0)
            elif "making_percentage" not in request.form and "making" in request.form:
                # An older form can still submit its original NPR field.
                p.making = decimal(request.form["making"], places=4)
                p.making_percentage = None
            elif not pid or p.making_percentage is not None:
                p.making_percentage = None
                p.making = Decimal(0)
            p.fixed = decimal(request.form.get("fixed"), places=4)
        names = sorted(
            {text(x, 60).lower() for x in request.form.get("tags", "").split(",") if x.strip()}
        )
        if len(names) > 20:
            raise ValueError("Use at most twenty tags")
        with db.session.no_autoflush:
            tags = []
            for name in names:
                db.session.execute(
                    insert(Tag).values(name=name).on_conflict_do_nothing(index_elements=["name"])
                )
                tags.append(db.session.scalar(select(Tag).where(Tag.name == name)))
        p.tags = tags
        p.search_text = " ".join([p.name, p.description, category.name, metal, purity_code or "", *names])
        db.session.add(p)
        db.session.flush()
        audit("product.saved", p.id)
        db.session.commit()
        return redirect("/merchant?tab=Products")
    return render_template(
        "edit_product.html",
        product=p,
        tola_grams=TOLA_GRAMS,
        categories=db.session.scalars(select(Category).order_by(Category.name)).all(),
    )


@merchant.post("/products/<uuid:pid>/publish")
@login_required
def publish(pid):
    once()
    p = owner_product(pid)
    s = locked_store(p.store_id)
    db.session.refresh(p)
    before = p.status
    if p.status in ("archived", "suspended", "excess"):
        raise ValueError("Administrator or plan restriction prevents publication")
    if p.status == "published":
        p.status = "draft"
        cancel_features(product_id=p.id)
    else:
        if not eligible(s):
            raise ValueError("An active verified store is required")
        if not any(m.kind == "image" and m.status == "ready" for m in p.media):
            raise ValueError("Upload at least one product image first")
        count = db.session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.store_id == s.id, Product.status == "published")
        )
        if count >= s.plan.products:
            raise ValueError("Published product allowance reached")
        p.status = "published"
    audit("product.status", p.id, previous=before, new=p.status)
    db.session.commit()
    return redirect("/merchant?tab=Products")


@merchant.post("/products/<uuid:pid>/media")
@login_required
def media_upload(pid):
    once()
    p = owner_product(pid)
    s = locked_store(p.store_id)
    if not s.active or p.status in ("archived", "suspended", "excess"):
        raise ValueError("Media changes are restricted")
    kind = request.form.get("kind")
    if kind not in ("image", "reel"):
        abort(400)
    edits = {
        "rotate": int(decimal(request.form.get("rotate", "0"), "0", "270", 0)),
        "square": request.form.get("square") == "1",
        "brightness": float(decimal(request.form.get("brightness", "1"), ".5", "1.5", 2)),
        "start": float(decimal(request.form.get("start", "0"), "0", "60", 2)),
        "end": float(decimal(request.form.get("end", "0") or "0", "0", "60", 2)),
        "mute": request.form.get("mute") == "1",
    }
    if edits["rotate"] not in (0, 90, 180, 270):
        raise ValueError("Choose a quarter-turn rotation")
    if kind == "reel" and edits["end"] and edits["end"] - edits["start"] < 5:
        raise ValueError("Select at least 5 seconds of video")
    upload(request.files.get("file"), s, kind, p, edits)
    db.session.commit()
    flash("Upload received. Reels appear after processing; refresh to check status.")
    return redirect("/merchant?tab=Products")


@merchant.post("/media/<uuid:mid>/remove")
@login_required
def remove_media(mid):
    once()
    m = db.get_or_404(Media, mid)
    s = locked_store(m.store_id)
    if s.owner_id != current_user.id or m.kind not in ("image", "reel"):
        abort(403)
    m.status = "suspended"
    if m.kind == "image":
        p = db.session.get(Product, m.product_id)
        p.status = "draft" if p.status == "published" else p.status
        cancel_features(product_id=p.id)
    audit("media.removed", m.id)
    db.session.commit()
    return redirect("/merchant?tab=Products")


@merchant.post("/profile")
@login_required
def profile():
    once()
    s = locked_store(my_store().id)
    before = s.surplus
    before_silver = s.silver_surplus
    lat, lon = coordinates(request.form.get("latitude"), request.form.get("longitude"))
    s.name = text(request.form.get("name"))
    s.phone = phone(request.form.get("phone", ""))
    s.email = text(request.form.get("email"), 254, False) or None
    if s.email and ("@" not in s.email or any(c.isspace() for c in s.email)):
        raise ValueError("Enter a valid store email")
    s.whatsapp = phone(request.form["whatsapp"]) if request.form.get("whatsapp", "").strip() else None
    s.address = text(request.form.get("address"), 500)
    s.latitude, s.longitude, s.location = lat, lon, f"SRID=4326;POINT({lon} {lat})"
    surplus_unit = request.form.get("surplus_unit", "gram")
    if surplus_unit not in ("gram", "tola"):
        raise ValueError("Choose Gram or Tola for surplus")
    divisor = TOLA_GRAMS if surplus_unit == "tola" else Decimal(1)
    s.surplus = (decimal(request.form.get("surplus"), places=4) / divisor).quantize(Decimal(".0001"))
    s.silver_surplus = (decimal(request.form.get("silver_surplus"), places=4) / divisor).quantize(Decimal(".0001")) if "silver_surplus" in request.form else s.silver_surplus
    audit(
        "store.profile",
        s.id,
        previous_surplus=before,
        new_surplus=s.surplus,
        previous_silver_surplus=before_silver,
        new_silver_surplus=s.silver_surplus,
        latitude=lat,
        longitude=lon,
    )
    db.session.commit()
    flash("Store profile saved.")
    return redirect("/merchant?tab=Store")


@merchant.post("/upgrade")
@login_required
def upgrade():
    once()
    s = locked_store(my_store().id)
    name = request.form.get("plan")
    if name not in ("Standard", "Premium") or name == s.plan_name:
        raise ValueError("Choose a different paid plan")
    if db.session.scalar(
        select(Upgrade).where(Upgrade.store_id == s.id, Upgrade.status == "pending")
    ):
        raise ValueError("An upgrade request is already pending")
    m = upload(request.files.get("evidence"), s, "payment")
    item = Upgrade(store_id=s.id, plan_name=name, evidence_id=m.id)
    db.session.add(item)
    db.session.flush()
    audit("upgrade.requested", item.id, plan=name)
    db.session.commit()
    return redirect("/merchant?tab=Subscription")


@merchant.post("/featured")
@login_required
def featured():
    once()
    s = my_store()
    p = owner_product(request.form.get("product_id"))
    start = datetime.fromisoformat(request.form.get("start", "")).replace(tzinfo=NEPAL)
    end = datetime.fromisoformat(request.form.get("end", "")).replace(tzinfo=NEPAL)
    schedule(s, p, start, end)
    db.session.commit()
    return redirect("/merchant?tab=Featured")


@merchant.post("/featured/<uuid:fid>/cancel")
@login_required
def cancel_feature_route(fid):
    once()
    f = db.get_or_404(Feature, fid)
    if f.store_id != my_store().id:
        abort(403)
    locked_store(f.store_id)
    db.session.refresh(f)
    cancel_feature(f)
    db.session.commit()
    return redirect("/merchant?tab=Featured")
