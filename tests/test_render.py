import uuid
from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace as NS

from flask import render_template


def test_populated_public_templates(app):
    now = datetime.now(timezone.utc)
    store = NS(
        id=uuid.uuid4(),
        name="Test Jeweller",
        latitude=D("27.704"),
        longitude=D("85.311"),
        phone="+9779800000001",
        surplus=D(100),
        address="Kathmandu",
    )
    p = NS(
        id=uuid.uuid4(),
        name="Gold ring",
        media=[],
        purity=D(".75"),
        weight=D(2),
        metal="Gold",
        store=store,
        store_id=store.id,
        tags=[],
        description="Handcrafted",
    )
    with app.test_request_context("/"):
        html = render_template(
            "discover.html",
            rows=[(p, D(15275), D(0))],
            more=False,
            page=1,
            spotlight=[(p, D(15275), None)],
            rates=[NS(metal="Gold", value=D(10000), updated_at=now)],
            banners=[
                NS(
                    title="Tradition, beautifully reimagined.",
                    eyebrow="THE BRIDAL EDIT",
                    href="/",
                    art="✦",
                )
            ],
            categories=[],
            active="discover",
        )
        assert "The Spotlight" in html and "15,275.00" in html
        assert "Gold ring" in render_template(
            "product.html",
            product=p,
            rate=NS(value=D(10000)),
            cost={
                "metal": D(15000),
                "surplus": D(200),
                "making": D(50),
                "fixed": D(25),
                "total": D(15275),
            },
            units=[NS(name="xyz", symbol="xyz", grams=D(".5"))],
        )


def test_populated_admin_templates(app):
    with app.test_request_context("/admin"):
        unit = NS(
            id=uuid.uuid4(), name="xyz", symbol="xyz", grams=D(".5"), description="", active=True
        )
        html = render_template(
            "admin.html",
            tab="Units",
            records=[unit],
            more=False,
            page=1,
            upgrades=[],
            stores=[],
            history=[],
        )
        assert "/admin/units/" + str(unit.id) in html


def test_merchant_and_admin_populated_views(app):
    sid = uuid.uuid4()
    pid = uuid.uuid4()
    mid = uuid.uuid4()
    ts = datetime.now(timezone.utc)
    plan = NS(name="Standard", products=80, reels=1, hours=20)
    owner = NS(name="Test Owner")
    store = NS(
        id=sid,
        name="Test Store",
        plan=plan,
        plan_name="Standard",
        owner=owner,
        address="Kathmandu",
        phone="+9779800000001",
        verification="verified",
        active=True,
        latitude=D("27.704"),
        longitude=D("85.311"),
        surplus=D(100),
    )
    media = NS(id=mid, kind="reel", status="ready", output="test.mp4", error=None)
    product = NS(id=pid, name="Test Ring", status="published", media=[media], store=store)
    media.product = product
    feature = NS(id=uuid.uuid4(), product=product, start=ts, end=ts, status="scheduled", slot=1)
    upgrade = NS(
        id=uuid.uuid4(), store=store, plan_name="Premium", evidence_id=mid, status="pending"
    )
    banner = NS(
        id=uuid.uuid4(),
        position=1,
        eyebrow="TEST",
        title="Test banner",
        art="✦",
        href="/",
        active=True,
    )
    with app.test_request_context("/"):
        for tab in ["Overview", "Products", "Media", "Featured", "Store", "Subscription"]:
            html = render_template(
                "merchant.html",
                store=store,
                products=[product],
                tab=tab,
                features=[feature],
                upgrades=[upgrade],
                plans=[plan],
            )
            assert "Test Store" in html
        cases = {
            "Stores": [store],
            "Products": [product],
            "Reels": [media],
            "Plans": [plan],
            "Featured": [feature],
            "Banners": [banner],
        }
        for tab, records in cases.items():
            html = render_template(
                "admin.html",
                tab=tab,
                records=records,
                page=1,
                more=False,
                stores=[store],
                upgrades=[upgrade],
                history=[],
            )
            assert "Administration" in html
