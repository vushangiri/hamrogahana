from flask import Blueprint, abort, redirect, render_template, request
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import Audit, Banner, Feature, Media, Plan, Product, Rate, Store, Unit, Upgrade, now
from .security import admin_only, once
from .services.core import (
    audit,
    cancel_feature,
    cancel_features,
    decimal,
    locked_store,
    set_plan,
    text,
)

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.get("/stores/<uuid:sid>")
@admin_only
def store_detail(sid):
    s = db.get_or_404(Store, sid)
    page = max(1, min(10000, int(request.args.get("page", 1))))
    query = select(Product).where(Product.store_id == sid)
    search = request.args.get("q", "").strip()[:150]
    if search:
        term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.where(Product.search_text.ilike(term, escape="\\"))
    products = db.session.scalars(
        query.order_by(Product.created_at.desc(), Product.id).limit(11).offset((page - 1) * 10)
    ).all()
    return render_template(
        "admin_store.html", store=s, products=products[:10], more=len(products) > 10, page=page,
        media=db.session.scalars(
            select(Media).where(Media.store_id == sid, Media.kind.in_(["document", "payment"]))
            .order_by(Media.created_at.desc(), Media.id)
        ).all(),
        upgrades=db.session.scalars(
            select(Upgrade).where(Upgrade.store_id == sid).order_by(Upgrade.created_at.desc())
        ).all(),
    )


@admin.get("/products/<uuid:pid>")
@admin_only
def product_detail(pid):
    from .routes import product_context

    p = db.get_or_404(Product, pid)
    return render_template("product.html", admin_detail=True, **product_context(p))


@admin.get("")
@admin_only
def dashboard():
    tab = request.args.get("tab", "Overview")
    tables = {
        "Stores": Store,
        "Products": Product,
        "Rates": Rate,
        "Units": Unit,
        "Plans": Plan,
        "Featured": Feature,
        "Audit": Audit,
        "Reels": Media,
        "Banners": Banner,
    }
    if tab not in ("Overview", *tables):
        abort(404)
    page = max(1, min(10000, int(request.args.get("page", 1))))
    model = tables.get(tab, Store)
    q = select(model)
    search = request.args.get("q", "").strip()[:150]
    if search and tab in ("Stores", "Products"):
        term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        from .models import User

        if tab == "Stores":
            q = q.where(or_(
                Store.name.ilike(term, escape="\\"),
                Store.phone.ilike(term, escape="\\"),
                Store.address.ilike(term, escape="\\"),
                Store.owner.has(or_(User.name.ilike(term, escape="\\"),
                                    User.phone.ilike(term, escape="\\"))),
            ))
        else:
            q = q.where(or_(
                Product.name.ilike(term, escape="\\"),
                Product.description.ilike(term, escape="\\"),
                Product.search_text.ilike(term, escape="\\"),
                Product.metal.ilike(term, escape="\\"),
                Product.store.has(Store.name.ilike(term, escape="\\")),
            ))
    if model is Store:
        q = q.options(joinedload(Store.owner))
    elif model is Product:
        q = q.options(joinedload(Product.store))
    elif model is Media:
        q = q.options(joinedload(Media.product))
    elif model is Feature:
        q = q.options(joinedload(Feature.product))
    if tab == "Overview":
        q = q.where(Store.verification == "pending")
    if tab == "Reels":
        q = q.where(Media.kind == "reel")
    if hasattr(model, "created_at"):
        q = q.order_by(model.created_at.desc(), model.id)
    records = db.session.scalars(q.limit(11).offset((page - 1) * 10)).all()
    return render_template(
        "admin.html",
        tab=tab,
        records=records[:10],
        more=len(records) > 10,
        page=page,
        upgrades=db.session.scalars(
            select(Upgrade)
            .options(joinedload(Upgrade.store))
            .where(Upgrade.status == "pending")
            .limit(50)
        ).all(),
        stores=db.session.scalars(select(Store).order_by(Store.created_at.desc()).limit(100)).all()
        if tab == "Plans"
        else [],
        history=db.session.scalars(
            select(Audit)
            .where(Audit.action == "rate.changed")
            .order_by(Audit.created_at.desc())
            .limit(50)
        ).all()
        if tab == "Rates"
        else [],
    )


@admin.post("/stores/<uuid:sid>")
@admin_only
def update_store(sid):
    once()
    s = locked_store(sid)
    action = request.form.get("action")
    before = f"{s.verification}/{s.active}"
    if action in ("verified", "rejected", "pending"):
        s.verification = action
    elif action in ("suspend", "reactivate"):
        s.active = action == "reactivate"
    else:
        abort(400)
    if not s.active or s.verification != "verified":
        cancel_features(store_id=s.id)
    audit(
        "store.status",
        s.id,
        previous=before,
        new=f"{s.verification}/{s.active}",
        reason=text(request.form.get("reason"), 500),
    )
    db.session.commit()
    return redirect("/admin?tab=Stores")


@admin.get("/stores/<uuid:sid>/documents")
@admin_only
def documents(sid):
    s = db.get_or_404(Store, sid)
    return render_template(
        "documents.html",
        store=s,
        media=db.session.scalars(
            select(Media).where(Media.store_id == sid, Media.kind == "document")
        ).all(),
    )


@admin.post("/products/<uuid:pid>")
@admin_only
def update_product(pid):
    once()
    p = db.get_or_404(Product, pid)
    locked_store(p.store_id)
    before = p.status
    status = request.form.get("status")
    if status not in ("archived", "suspended", "draft"):
        abort(400)
    p.status = status
    cancel_features(product_id=p.id)
    audit(
        "product.admin_status",
        p.id,
        previous=before,
        new=status,
        reason=text(request.form.get("reason"), 500),
    )
    db.session.commit()
    return redirect("/admin?tab=Products")


@admin.post("/rates")
@admin_only
def rates():
    once()
    reason = text(request.form.get("reason"), 500)
    for metal in ("Gold", "Silver"):
        rate = db.session.scalar(select(Rate).where(Rate.metal == metal).with_for_update())
        value = decimal(request.form.get(metal), ".0001", places=4)
        audit("rate.changed", metal, previous=rate.value, new=value, reason=reason)
        rate.value, rate.updated_at = value, now()
        from .services.core import NEPAL
        rate.effective_date = rate.updated_at.astimezone(NEPAL).date()
        rate.source = "manual"
        rate.per_ten_grams = rate.per_tola = None
    db.session.commit()
    return redirect("/admin?tab=Rates")


@admin.post("/units")
@admin.post("/units/<uuid:uid>")
@admin_only
def units(uid=None):
    once()
    from .models import DisplaySettings
    settings = db.session.scalar(select(DisplaySettings).where(DisplaySettings.id == 1).with_for_update())
    u = db.get_or_404(Unit, uid) if uid else Unit()
    u.name = text(request.form.get("name"), 80)
    u.symbol = text(request.form.get("symbol"), 20)
    u.grams = decimal(request.form.get("grams"), ".0000000001", "100000", 10)
    u.description = text(request.form.get("description"), 500, False)
    u.active = request.form.get("active") == "on"
    if settings and settings.default_unit_id == u.id and not u.active:
        raise ValueError("Choose another default unit before disabling this unit")
    db.session.add(u)
    db.session.flush()
    audit("unit.saved", u.id, grams=u.grams, active=u.active)
    db.session.commit()
    return redirect("/admin?tab=Units")


@admin.post("/subscriptions/<uuid:sid>")
@admin_only
def subscriptions(sid):
    once()
    s = locked_store(sid)
    set_plan(s, request.form.get("plan"))
    db.session.commit()
    return redirect("/admin?tab=Plans")


@admin.post("/upgrades/<uuid:uid>")
@admin_only
def upgrades(uid):
    once()
    item = db.get_or_404(Upgrade, uid)
    s = locked_store(item.store_id)
    db.session.refresh(item)
    if item.status != "pending":
        raise ValueError("Request already reviewed")
    action = request.form.get("action")
    if action not in ("approved", "rejected"):
        abort(400)
    if action == "approved":
        set_plan(s, item.plan_name)
    item.status = action
    audit("upgrade.reviewed", item.id, status=action)
    db.session.commit()
    return redirect("/admin?tab=Plans")


@admin.post("/featured/<uuid:fid>/cancel")
@admin_only
def featured(fid):
    once()
    f = db.get_or_404(Feature, fid)
    locked_store(f.store_id)
    db.session.refresh(f)
    cancel_feature(f)
    db.session.commit()
    return redirect("/admin?tab=Featured")


@admin.post("/reels/<uuid:mid>")
@admin_only
def reels(mid):
    once()
    m = db.get_or_404(Media, mid)
    locked_store(m.store_id)
    if m.kind != "reel":
        abort(400)
    m.status = "suspended"
    audit("reel.suspended", m.id, reason=text(request.form.get("reason"), 500))
    db.session.commit()
    return redirect("/admin?tab=Reels")


@admin.post("/banners/<uuid:bid>")
@admin_only
def banners(bid):
    once()
    b = db.get_or_404(Banner, bid)
    b.title = text(request.form.get("title"), 160)
    b.eyebrow = text(request.form.get("eyebrow"), 80)
    b.art = text(request.form.get("art"), 20)
    href = text(request.form.get("href"), 500)
    if (
        not href.startswith("/")
        or href.startswith("//")
        or "\\" in href
        or any(ord(c) < 32 for c in href)
    ):
        raise ValueError("Banner target must be a local application path")
    b.href = href
    b.active = request.form.get("active") == "on"
    audit("banner.updated", b.id)
    db.session.commit()
    return redirect("/admin?tab=Banners")


@admin.post("/plans/<name>")
@admin_only
def plan_limits(name):
    once()
    plan = db.get_or_404(Plan, name)
    products = int(decimal(request.form.get("products"), "1", "10000", 0))
    reels = int(decimal(request.form.get("reels"), "0", "20", 0))
    hours = int(decimal(request.form.get("hours"), "0", "168", 0))
    affected = db.session.scalars(
        select(Store).where(Store.plan_name == name).order_by(Store.id).with_for_update()
    ).all()
    old = f"{plan.products}/{plan.reels}/{plan.hours}"
    plan.products, plan.reels, plan.hours = products, reels, hours
    db.session.flush()
    for store in affected:
        set_plan(store, name)
    audit("plan.entitlements", name, previous=old, new=f"{products}/{reels}/{hours}")
    db.session.commit()
    return redirect("/admin?tab=Plans")


@admin.post("/featured")
@admin_only
def create_feature():
    import uuid
    from datetime import datetime

    from .services.core import NEPAL, schedule

    once()
    product = db.get_or_404(Product, uuid.UUID(request.form.get("product_id", "")))
    start = datetime.fromisoformat(request.form.get("start", "")).replace(tzinfo=NEPAL)
    end = datetime.fromisoformat(request.form.get("end", "")).replace(tzinfo=NEPAL)
    schedule(product.store, product, start, end)
    db.session.commit()
    return redirect("/admin?tab=Featured")


@admin.get("/password-resets")
@admin_only
def password_resets():
    from .models import PasswordReset, User

    page = max(1, min(10000, int(request.args.get("page", 1))))
    items = db.session.scalars(select(PasswordReset).order_by(
        (PasswordReset.status == "pending").desc(), PasswordReset.created_at.desc(),
        PasswordReset.id).limit(21).offset((page - 1) * 20)).all()
    accounts = {user.phone: (user, store) for user, store in db.session.execute(
        select(User, Store).outerjoin(Store, Store.owner_id == User.id)
        .where(User.phone.in_([item.phone for item in items])))}
    return render_template("password_resets.html", items=items[:20],
                           accounts=accounts, page=page, more=len(items) > 20)


@admin.post("/password-resets/<uuid:rid>")
@admin_only
def review_password_reset(rid):
    import secrets
    import string

    from flask_login import current_user
    from werkzeug.security import generate_password_hash
    from .models import PasswordReset, User

    once()
    item = db.session.scalar(select(PasswordReset).where(PasswordReset.id == rid)
                             .with_for_update().execution_options(populate_existing=True))
    if not item:
        abort(404)
    if item.status != "pending":
        raise ValueError("This request has already been reviewed")
    action = request.form.get("action")
    if action not in ("approved", "rejected"):
        abort(400)
    generated = None
    if action == "approved":
        user = db.session.scalar(select(User).where(User.phone == item.phone).with_for_update())
        if not user:
            raise ValueError("No account exists for this phone number; reject the request")
        generated = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        user.password_hash = generate_password_hash(generated)
    item.status, item.reviewed_at, item.reviewer_id = action, now(), current_user.id
    audit("password_reset.reviewed", item.id, status=action)
    db.session.commit()
    if generated:
        # Never persist plaintext passwords in sessions, notifications, or audit logs.
        response = render_template("password_reset_generated.html", password=generated, phone=item.phone)
        return response, 200, {"Cache-Control": "no-store", "Pragma": "no-cache"}
    return redirect("/admin/password-resets")


@admin.post("/units/default")
@admin_only
def default_unit():
    import uuid
    from .models import DisplaySettings

    once()
    settings = db.session.scalar(select(DisplaySettings).where(DisplaySettings.id == 1).with_for_update())
    selected = request.form.get("unit", "gram")
    if selected == "gram":
        uid = None
    else:
        unit = db.session.scalar(select(Unit).where(Unit.id == uuid.UUID(selected)).with_for_update())
        if not unit or not unit.active:
            raise ValueError("Choose an active unit")
        uid = unit.id
    settings.default_unit_id = uid
    audit("unit.default", uid or "gram")
    db.session.commit()
    return redirect("/admin?tab=Units")
