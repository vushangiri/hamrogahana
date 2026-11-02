import re
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import abort
from flask_login import current_user
from sqlalchemy import func, select

from ..extensions import db
from ..models import Audit, Feature, Media, Plan, Product, Store, now

NEPAL = ZoneInfo("Asia/Kathmandu")


def decimal(value, minimum="0", maximum="100000000000", places=None):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not Decimal(minimum) <= number <= Decimal(maximum):
            raise ValueError("Number outside allowed range")
        if places is not None and number != number.quantize(Decimal(1).scaleb(-places)):
            raise ValueError(f"Use at most {places} decimal places")
        return number
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid number") from None


def money(value):
    return Decimal(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def breakdown(rate, purity, weight, surplus, making, fixed):
    metal = rate * purity * weight
    extra = surplus * weight
    return {
        "metal": money(metal),
        "surplus": money(extra),
        "making": money(making),
        "fixed": money(fixed),
        "total": money(metal + extra + making + fixed),
    }


def phone(value):
    value = re.sub(r"[\s()-]", "", value)
    if re.fullmatch(r"9[678]\d{8}", value):
        value = "+977" + value
    if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
        raise ValueError("Use a valid international phone number, or a Nepal mobile number")
    return value


def text(value, maximum=150, required=True):
    value = str(value or "").strip()
    if len(value) > maximum or (required and not value):
        raise ValueError(f"Enter text between {1 if required else 0} and {maximum} characters")
    return value


def coordinates(lat, lon):
    return decimal(lat, "-90", "90", 7), decimal(lon, "-180", "180", 7)


def audit(action, entity, **detail):
    db.session.add(
        Audit(
            actor_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            entity_id=str(entity),
            detail={k: str(v) for k, v in detail.items()},
        )
    )


def locked_store(store_id):
    return db.session.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one()


def eligible(store):
    return store.active and store.verification == "verified"


def cancel_feature(item):
    """Release only unused time; retain delivered time in weekly quota history."""
    timestamp = now()
    if item.status != "scheduled" or item.end <= timestamp:
        return
    original_end = item.end
    if item.start < timestamp:
        item.end = timestamp
    else:
        item.status = "cancelled"
    audit("feature.cancelled", item.id, original_end=original_end, retained_end=item.end)


def cancel_features(store_id=None, product_id=None):
    q = select(Feature).where(Feature.status == "scheduled", Feature.end > now())
    q = (
        q.where(Feature.store_id == store_id)
        if store_id
        else q.where(Feature.product_id == product_id)
    )
    for feature in db.session.scalars(q):
        cancel_feature(feature)


def set_plan(store, name):
    plan = db.session.get(Plan, name)
    if not plan:
        raise ValueError("Unknown plan")
    old = store.plan_name
    store.plan_name = name
    products = db.session.scalars(
        select(Product).where(Product.store_id == store.id).order_by(Product.created_at, Product.id)
    ).all()
    for p in products[plan.products :]:
        if p.status not in ("archived", "suspended"):
            p.status = "excess"
    for p in products:
        reels = db.session.scalars(
            select(Media)
            .where(
                Media.product_id == p.id,
                Media.kind == "reel",
                Media.status.in_(["queued", "processing", "ready"]),
            )
            .order_by(Media.created_at, Media.id)
        ).all()
        for reel in reels[plan.reels :]:
            reel.status = "excess"
    cancel_features(store_id=store.id)
    audit("subscription.changed", store.id, previous=old, new=name)


def week_slices(start, end):
    cursor = start.astimezone(NEPAL)
    end = end.astimezone(NEPAL)
    while cursor < end:
        monday = (cursor - timedelta(days=cursor.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stop = min(end, monday + timedelta(days=7))
        yield (
            monday,
            monday + timedelta(days=7),
            Decimal(str((stop - cursor).total_seconds())) / 3600,
        )
        cursor = stop


def schedule(store, product, start, end):
    # Serialize all capacity decisions, then lock the store. All callers use this order.
    db.session.execute(select(func.pg_advisory_xact_lock(604217)))
    store = locked_store(store.id)
    db.session.refresh(product)
    if product.store_id != store.id or product.status != "published" or not eligible(store):
        raise ValueError("Product is not eligible")
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or start < now()
        or end <= start
        or end - start > timedelta(days=7)
        or start > now() + timedelta(days=90)
    ):
        raise ValueError("Choose a future window, at most 7 days long, within 90 days")
    limit = db.session.get(Plan, store.plan_name).hours
    for monday, next_monday, hours in week_slices(start, end):
        existing = db.session.scalars(
            select(Feature).where(
                Feature.store_id == store.id,
                Feature.status == "scheduled",
                Feature.start < next_monday,
                Feature.end > monday,
            )
        ).all()
        used = sum(
            (
                Decimal(str((min(f.end, next_monday) - max(f.start, monday)).total_seconds()))
                / 3600
                for f in existing
            ),
            Decimal(0),
        )
        if used + hours > limit:
            raise ValueError("Weekly featured allowance exceeded")
    overlaps = db.session.scalars(
        select(Feature).where(
            Feature.status == "scheduled", Feature.start < end, Feature.end > start
        )
    ).all()
    if any(f.product_id == product.id for f in overlaps):
        raise ValueError("This product already has an overlapping placement")
    slot = next((i for i in range(1, 7) if i not in {f.slot for f in overlaps}), None)
    if slot is None:
        raise ValueError("All six slots are occupied during this window")
    item = Feature(store_id=store.id, product_id=product.id, start=start, end=end, slot=slot)
    db.session.add(item)
    db.session.flush()
    audit("feature.scheduled", item.id, start=start, end=end, hours=str(end - start))
    return item


def owner_product(product_id):
    import uuid

    product_id = uuid.UUID(str(product_id))
    p = db.get_or_404(Product, product_id)
    if p.store.owner_id != current_user.id:
        abort(403)
    return p
