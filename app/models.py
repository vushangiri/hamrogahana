"""PostgreSQL domain model. UUID identity, NUMERIC money, immutable audit history."""

import uuid
from datetime import datetime, timezone

from flask_login import UserMixin
from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB

from .extensions import db


def now():
    return datetime.now(timezone.utc)


class Base(db.Model):
    __abstract__ = True
    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)


class User(UserMixin, Base):
    phone = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254))
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(16), nullable=False, default="merchant")
    __table_args__ = (CheckConstraint("role IN ('merchant','admin')"),)


class Plan(db.Model):
    name = db.Column(db.String(16), primary_key=True)
    products = db.Column(db.Integer, nullable=False)
    reels = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Integer, nullable=False)
    __table_args__ = (CheckConstraint("products > 0 AND reels >= 0 AND hours >= 0"),)


class Store(Base):
    owner_id = db.Column(db.Uuid, db.ForeignKey("user.id"), unique=True, nullable=False)
    owner = db.relationship(User)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(254))
    whatsapp = db.Column(db.String(20))
    address = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Numeric(10, 7), nullable=False)
    longitude = db.Column(db.Numeric(10, 7), nullable=False)
    location = db.Column(Geography("POINT", srid=4326), nullable=False)
    surplus = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    verification = db.Column(db.String(16), nullable=False, default="pending", index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    plan_name = db.Column(db.String(16), db.ForeignKey("plan.name"), nullable=False, default="Free")
    plan = db.relationship(Plan)
    __table_args__ = (
        CheckConstraint("surplus >= 0"),
        CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180"),
        CheckConstraint("verification IN ('pending','verified','rejected')"),
    )


class Category(Base):
    name = db.Column(db.String(80), nullable=False, unique=True)


product_tag = db.Table(
    "product_tag",
    db.Column("product_id", db.Uuid, db.ForeignKey("product.id"), primary_key=True),
    db.Column("tag_id", db.Uuid, db.ForeignKey("tag.id"), primary_key=True),
)


class Tag(Base):
    name = db.Column(db.String(60), nullable=False, unique=True)


class Notification(Base):
    user_id = db.Column(db.Uuid, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False)
    href = db.Column(db.String(500), nullable=False, default="/notifications")
    read_at = db.Column(db.DateTime(timezone=True))


class RateSync(db.Model):
    day = db.Column(db.Date, primary_key=True)
    checked_at = db.Column(db.DateTime(timezone=True), nullable=False)


class Rate(db.Model):
    metal = db.Column(db.String(10), primary_key=True)
    effective_date = db.Column(db.Date)
    source = db.Column(db.String(20), nullable=False, default="manual")
    per_ten_grams = db.Column(db.Numeric(18, 4))
    per_tola = db.Column(db.Numeric(18, 4))
    value = db.Column(db.Numeric(18, 4), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (CheckConstraint("value > 0"), CheckConstraint("metal IN ('Gold','Silver')"))


class Product(Base):
    store_id = db.Column(db.Uuid, db.ForeignKey("store.id"), nullable=False, index=True)
    store = db.relationship(Store)
    category_id = db.Column(db.Uuid, db.ForeignKey("category.id"), nullable=False, index=True)
    category = db.relationship(Category)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    metal = db.Column(db.String(10), db.ForeignKey("rate.metal"), nullable=False, index=True)
    purity = db.Column(db.Numeric(12, 10), nullable=False)
    weight = db.Column(db.Numeric(16, 6), nullable=False)
    making = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    fixed = db.Column(db.Numeric(18, 4), nullable=False, default=0)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    search_text = db.Column(db.Text, nullable=False, default="")
    tags = db.relationship(Tag, secondary=product_tag, lazy="selectin")
    media = db.relationship("Media", lazy="selectin", order_by="Media.created_at")
    __table_args__ = (
        CheckConstraint("weight > 0 AND purity > 0 AND purity <= 1 AND making >= 0 AND fixed >= 0"),
        CheckConstraint("status IN ('draft','published','archived','suspended','excess')"),
        Index("ix_product_catalogue", "status", "metal", "category_id", "created_at"),
    )


class Unit(Base):
    name = db.Column(db.String(80), nullable=False, unique=True)
    symbol = db.Column(db.String(20), nullable=False, unique=True)
    grams = db.Column(db.Numeric(20, 10), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    description = db.Column(db.String(500), nullable=False, default="")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now, onupdate=now)
    __table_args__ = (CheckConstraint("grams > 0"),)


class Media(Base):
    product_id = db.Column(db.Uuid, db.ForeignKey("product.id"), index=True)
    store_id = db.Column(db.Uuid, db.ForeignKey("store.id"), nullable=False, index=True)
    product = db.relationship(Product, overlaps="media")
    kind = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="queued")
    source = db.Column(db.String(120), nullable=False)
    output = db.Column(db.String(120))
    thumbnail = db.Column(db.String(120))
    variants = db.Column(JSONB, nullable=False, default=dict)
    error = db.Column(db.String(500))
    __table_args__ = (
        CheckConstraint("kind IN ('image','reel','document','payment')"),
        CheckConstraint("status IN ('queued','processing','ready','failed','suspended','excess')"),
    )


class Job(Base):
    media_id = db.Column(db.Uuid, db.ForeignKey("media.id"), unique=True, nullable=False)
    state = db.Column(db.String(16), nullable=False, default="queued", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    leased_at = db.Column(db.DateTime(timezone=True))
    token = db.Column(db.Uuid)
    error = db.Column(db.String(500))


class Upgrade(Base):
    store_id = db.Column(db.Uuid, db.ForeignKey("store.id"), nullable=False)
    store = db.relationship(Store)
    plan_name = db.Column(db.String(16), db.ForeignKey("plan.name"), nullable=False)
    evidence_id = db.Column(db.Uuid, db.ForeignKey("media.id"), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")


class Feature(Base):
    store_id = db.Column(db.Uuid, db.ForeignKey("store.id"), nullable=False, index=True)
    product_id = db.Column(db.Uuid, db.ForeignKey("product.id"), nullable=False)
    product = db.relationship(Product)
    start = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end = db.Column(db.DateTime(timezone=True), nullable=False)
    slot = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="scheduled")
    __table_args__ = (CheckConstraint('"end" > start'), CheckConstraint("slot BETWEEN 1 AND 6"))


class Delivery(Base):
    feature_id = db.Column(db.Uuid, db.ForeignKey("feature.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False)
    impressions = db.Column(db.BigInteger, nullable=False, default=1)
    __table_args__ = (db.UniqueConstraint("feature_id", "day"),)


class Banner(Base):
    position = db.Column(db.Integer, nullable=False, unique=True)
    eyebrow = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    art = db.Column(db.String(20), nullable=False, default="✦")
    href = db.Column(db.String(500), nullable=False, default="/")
    active = db.Column(db.Boolean, nullable=False, default=True)
    __table_args__ = (CheckConstraint("position BETWEEN 1 AND 6"),)


class Audit(Base):
    actor_id = db.Column(db.Uuid, db.ForeignKey("user.id"))
    action = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.String(80), nullable=False)
    detail = db.Column(JSONB, nullable=False, default=dict)


class Throttle(db.Model):
    key = db.Column(db.String(128), primary_key=True)
    count = db.Column(db.Integer, nullable=False)
    expires = db.Column(db.DateTime(timezone=True), nullable=False)


class GeoCache(db.Model):
    query = db.Column(db.String(200), primary_key=True)
    results = db.Column(JSONB, nullable=False)
    expires = db.Column(db.DateTime(timezone=True), nullable=False)


class Mutation(db.Model):
    key = db.Column(db.Uuid, primary_key=True)
    actor_id = db.Column(db.Uuid, db.ForeignKey("user.id"), nullable=False)
    path = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now)
