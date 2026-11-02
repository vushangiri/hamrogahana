from datetime import datetime
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .extensions import db
from .models import Category, Feature, Media, Plan, Product, Store, Tag, Upgrade
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
    schedule,
    text,
)
from .services.media import upload

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
    products = db.session.scalars(
        select(Product).where(Product.store_id == s.id).order_by(Product.created_at, Product.id)
    ).all()
    return render_template(
        "merchant.html",
        store=s,
        products=products,
        tab=tab,
        features=db.session.scalars(
            select(Feature)
            .where(Feature.store_id == s.id)
            .order_by(Feature.start.desc())
            .limit(100)
        ).all(),
        upgrades=db.session.scalars(
            select(Upgrade)
            .where(Upgrade.store_id == s.id)
            .order_by(Upgrade.created_at.desc())
            .limit(50)
        ).all(),
        plans=db.session.scalars(select(Plan).order_by(Plan.products)).all(),
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
        p.name = text(request.form.get("name"))
        p.description = text(request.form.get("description"), 5000, False)
        import uuid

        category = db.get_or_404(Category, uuid.UUID(request.form.get("category_id", "")))
        p.category_id = category.id
        metal = request.form.get("metal")
        purity_code = request.form.get("purity")
        allowed = {
            "Gold": {"24K": Decimal(1), "22K": Decimal(22) / 24, "18K": Decimal(".75")},
            "Silver": {"999": Decimal(".999"), "925": Decimal(".925")},
        }
        if metal not in allowed or purity_code not in allowed[metal]:
            raise ValueError("Choose a valid metal and purity combination")
        p.metal, p.purity = metal, allowed[metal][purity_code].quantize(Decimal(".0000000001"))
        p.weight = decimal(request.form.get("weight"), ".000001", "100000", 6)
        p.making = decimal(request.form.get("making"), places=4)
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
        p.search_text = " ".join([p.name, p.description, category.name, metal, purity_code, *names])
        db.session.add(p)
        db.session.flush()
        audit("product.saved", p.id)
        db.session.commit()
        return redirect("/merchant?tab=Products")
    return render_template(
        "edit_product.html",
        product=p,
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
    upload(request.files.get("file"), s, kind, p)
    db.session.commit()
    flash("Upload received. Reels appear after processing; refresh to check status.")
    return redirect("/merchant?tab=Media")


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
    return redirect("/merchant?tab=Media")


@merchant.post("/profile")
@login_required
def profile():
    once()
    s = locked_store(my_store().id)
    before = s.surplus
    lat, lon = coordinates(request.form.get("latitude"), request.form.get("longitude"))
    s.name = text(request.form.get("name"))
    s.phone = phone(request.form.get("phone", ""))
    s.address = text(request.form.get("address"), 500)
    s.latitude, s.longitude, s.location = lat, lon, f"SRID=4326;POINT({lon} {lat})"
    s.surplus = decimal(request.form.get("surplus"), places=4)
    audit(
        "store.profile",
        s.id,
        previous_surplus=before,
        new_surplus=s.surplus,
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
