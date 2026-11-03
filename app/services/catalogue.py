from sqlalchemy import Numeric, cast, func, literal, select
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import Feature, Product, Rate, Store, Tag, now
from .core import coordinates, decimal


def public_conditions():
    return Product.status == "published", Store.active.is_(True), Store.verification == "verified"


def price_expression():
    return cast(
        func.round(
            Rate.value * Product.purity * Product.weight
            + Store.surplus * Product.weight
            + Product.making
            + Product.fixed,
            2,
        ),
        Numeric(24, 2),
    )


def catalogue(args, page_size=10, store_id=None):
    filters = list(public_conditions())
    if store_id is None:
        lat, lon = coordinates(args.get("lat", "27.704"), args.get("lon", "85.311"))
        radius = decimal(args.get("radius", "50"), ".1", "1000")
        point = func.ST_GeogFromText(f"SRID=4326;POINT({lon} {lat})")
        distance = func.ST_Distance(Store.location, point)
        filters.append(func.ST_DWithin(Store.location, point, radius * 1000))
    else:
        # A store's own catalogue includes its full published range, regardless of location.
        distance = cast(literal(None), Numeric)
        filters.append(Product.store_id == store_id)
    price = price_expression()
    q = str(args.get("q", "")).strip()[:150]
    if q:
        term = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        match = Product.search_text.ilike(term, escape="\\")
        filters.append(match if store_id else match | Store.name.ilike(term, escape="\\"))
    for param, column in [("category", Product.category_id), ("store", Product.store_id)]:
        if args.get(param):
            import uuid

            try:
                filters.append(column == uuid.UUID(args[param]))
            except ValueError:
                raise ValueError("Invalid filter identifier") from None
    if args.get("metal"):
        filters.append(Product.metal == args["metal"])
    if args.get("purity"):
        filters.append(Product.purity == decimal(args["purity"], ".001", "1"))
    for tag in str(args.get("tags", "")).lower().split(",")[:10]:
        if tag.strip():
            filters.append(Product.tags.any(Tag.name == tag.strip()))
    for field, col in [("price", price), ("weight", Product.weight)]:
        for bound, op in [("min", "__ge__"), ("max", "__le__")]:
            if args.get(f"{field}_{bound}"):
                filters.append(getattr(col, op)(decimal(args[f"{field}_{bound}"])))
    if args.get("featured"):
        filters.append(
            select(Feature.id)
            .where(
                Feature.product_id == Product.id,
                Feature.status == "scheduled",
                Feature.start <= now(),
                Feature.end > now(),
            )
            .exists()
        )
    if args.get("ids"):
        import uuid

        try:
            filters.append(Product.id.in_([uuid.UUID(x) for x in args["ids"].split(",")[:100]]))
        except ValueError:
            raise ValueError("Invalid saved product identifier") from None
    order = {
        "low": (price.asc(), Product.id),
        "high": (price.desc(), Product.id),
        "new": (Product.created_at.desc(), Product.id),
    }.get(args.get("sort"), (distance, Product.id))
    base = (
        select(
            Product.id.label("pid"),
            distance.label("distance"),
            price.label("price"),
            func.row_number().over(partition_by=Product.store_id, order_by=order).label("turn"),
        )
        .join(Store)
        .join(Rate, Rate.metal == Product.metal)
        .where(*filters)
        .subquery()
    )
    # Default discovery interleaves store turns, then distance, deterministically.
    ordering = (
        (base.c.turn, base.c.distance, Product.id) if args.get("sort", "near") == "near" else order
    )
    stmt = (
        select(Product, base.c.price, base.c.distance)
        .join(base, base.c.pid == Product.id)
        .join(Store)
        .join(Rate, Rate.metal == Product.metal)
        .options(
            joinedload(Product.store),
            joinedload(Product.category),
            selectinload(Product.media),
            selectinload(Product.tags),
        )
        .order_by(*ordering)
    )
    try:
        page = max(1, min(10000, int(args.get("page", 1))))
    except ValueError:
        raise ValueError("Invalid page number") from None
    rows = db.session.execute(stmt.limit(page_size + 1).offset((page - 1) * page_size)).all()
    return rows[:page_size], len(rows) > page_size, page
