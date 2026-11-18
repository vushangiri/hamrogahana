from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Notification, Rate, RateSync, Store
from app.services.core import NEPAL
from app.services.rates import TOLA_GRAMS, parse_rates, sync_rates


def feed(day="2026-11-03"):
    return [dict(rateType=label, todayDate=f"{day}T04:50:07+00:00", todayBaseRatePerGram=value) for label, value in [("छापावाल सुन (१० ग्राम)",235770),("छापावाल सुन (१ तोला)",275000),("असली चाँदी दर (१० ग्राम)",3151),("असली चाँदी दर (१ तोला)",3675)]]


def test_feed_units_and_dates():
    day = datetime(2026,11,3).date()
    assert parse_rates(feed(),day)["Gold"] == {"tola": Decimal("275000")}
    assert parse_rates([row for row in feed() if "१ तोला" in row["rateType"]], day)["Silver"]["tola"] == Decimal("3675")
    for payload in (feed()[:3], feed("2026-11-02"), {}, feed()+feed()):
        with pytest.raises(ValueError):
            parse_rates(payload,day)


def login(client, uid):
    with client.session_transaction() as session:
        session["_user_id"] = str(uid)
        session["_fresh"] = True


def test_daily_import_manual_precedence_and_failure(database, monkeypatch):
    import uuid
    at = datetime(2026,11,3,10,46,tzinfo=NEPAL)
    for rate in db.session.scalars(select(Rate)):
        rate.updated_at = datetime(2026,11,2,tzinfo=NEPAL)
    db.session.commit()
    monkeypatch.setattr("app.services.rates.requests.get", lambda *a, **kw: SimpleNamespace(raise_for_status=lambda:None,json=feed))
    assert sync_rates(at)
    gold=db.session.get(Rate,"Gold")
    assert gold.value==(Decimal("275000") / TOLA_GRAMS).quantize(Decimal(".0001")) and gold.per_tola==Decimal("275000")
    assert gold.effective_date==at.date()
    c=database.test_client()
    login(c,database.config["TEST_ADMIN_ID"])
    assert c.post("/admin/rates",data={"mutation":str(uuid.uuid4()),"Gold":"24000","Silver":"320","reason":"Manual adjustment"}).status_code==302
    assert not sync_rates(at)
    assert db.session.get(Rate,"Gold").value==Decimal("24000")
    assert db.session.get(Rate,"Gold").source=="manual"
    monkeypatch.setattr("app.services.rates.requests.get", lambda *a, **kw: SimpleNamespace(raise_for_status=lambda:None,json=lambda:feed("2026-11-02")))
    with pytest.raises(ValueError):
        sync_rates(datetime(2026,11,4,10,46,tzinfo=NEPAL))
    db.session.rollback()
    assert db.session.get(Rate,"Gold").value==Decimal("24000")
    assert db.session.get(RateSync,datetime(2026,11,4).date()) is None
    assert not sync_rates(datetime(2026,11,4,11,16,tzinfo=NEPAL))


def test_private_inbox_and_public_contacts(database):
    import uuid
    c=database.test_client()
    item=Notification(user_id=database.config["TEST_OWNER_ID"],message="Private owner update",href="/merchant")
    db.session.add(item)
    db.session.commit()
    nid=item.id
    login(c,database.config["TEST_ADMIN_ID"])
    assert b"Private owner update" not in c.get("/notifications").data
    assert c.post(f"/notifications/{nid}/read").status_code==404
    sid=database.config["TEST_STORE_ID"]
    assert c.post(f"/admin/stores/{sid}",data={"mutation":str(uuid.uuid4()),"action":"verified","reason":"Reviewed"}).status_code==302
    login(c,database.config["TEST_OWNER_ID"])
    assert b"Your store status" in c.get("/notifications").data
    assert c.post(f"/notifications/{nid}/read").status_code==302
    assert db.session.get(Notification,nid).read_at is not None
    store=db.session.get(Store,sid)
    store.whatsapp="+9779800000001"
    store.email="store@example.com"
    db.session.commit()
    html=c.get(f"/stores/{sid}").data
    for link in (b"sms:",b"tel:",b"https://wa.me/9779800000001",b"mailto:store@example.com",b"google.com/maps/search/"):
        assert link in html


def test_manual_update_during_fetch_wins(database, monkeypatch):
    from datetime import timedelta

    at = datetime(2026,11,3,10,46,tzinfo=NEPAL)
    for rate in db.session.scalars(select(Rate)):
        rate.updated_at = at - timedelta(days=1)
    db.session.commit()

    def fetch(*args, **kwargs):
        gold = db.session.get(Rate,"Gold")
        gold.value = Decimal("25000")
        gold.updated_at = at + timedelta(seconds=1)
        gold.effective_date = at.date()
        gold.source = "manual"
        db.session.commit()
        return SimpleNamespace(raise_for_status=lambda:None,json=feed)

    monkeypatch.setattr("app.services.rates.requests.get",fetch)
    assert sync_rates(at)
    assert db.session.get(Rate,"Gold").value == Decimal("25000")
    assert db.session.get(Rate,"Gold").source == "manual"
    assert db.session.get(Rate,"Silver").value == (Decimal("3675") / TOLA_GRAMS).quantize(Decimal(".0001"))


def test_product_options_and_empty_saved(database):
    import uuid
    from app.models import Category, Product
    from app.services.catalogue import catalogue

    c = database.test_client()
    login(c, database.config["TEST_OWNER_ID"])
    category = db.session.scalar(select(Category))
    def create(**fields):
        return c.post('/merchant/products/new', data={
            'mutation': str(uuid.uuid4()), 'category_id': str(category.id),
            'name': 'Tola ring', 'description': 'Handmade ring', 'metal': 'Gold',
            'purity': '24K', 'weight': '1', 'weight_unit': 'tola',
            'making': '50', 'fixed': '100', **fields,
        })
    assert create().status_code == 302
    ring = db.session.scalar(select(Product).where(Product.name == 'Tola ring'))
    assert ring.weight == TOLA_GRAMS and ring.weight_unit == 'tola'
    assert create(metal='Other', description='Handmade bead necklace', fixed='2500',
                  name='', category_id='', weight='', purity='').status_code == 302
    other = db.session.scalar(select(Product).where(Product.metal == 'Other'))
    assert other.fixed == 2500
    ring.status = other.status = 'published'
    db.session.commit()
    assert b'Handmade bead necklace' in c.get('/?metal=Other').data
    assert b'Rs. 2,500.00' in c.get(f'/products/{other.id}').data
    assert catalogue({'ids': ''})[0] == []
    assert len(catalogue({'ids': str(other.id)})[0]) == 1
    assert create(metal='Other', description='').status_code == 400
    response = c.post('/merchant/profile', data={
        'mutation': str(uuid.uuid4()), 'name': 'Test Jeweller', 'phone': '+9779800000001',
        'address': 'Kathmandu', 'latitude': '27.704', 'longitude': '85.311',
        'surplus': '1166.38', 'silver_surplus': '116.638', 'surplus_unit': 'tola',
    })
    assert response.status_code == 302
    store = db.session.get(Store, database.config['TEST_STORE_ID'])
    assert store.surplus == 100 and store.silver_surplus == 10
    assert b'Photos & videos' in c.get('/merchant?tab=Products').data


def test_saved_distances_use_explicit_location_and_do_not_filter_by_radius(database):
    from app.models import Category, Product
    c=database.test_client()
    store=db.session.get(Store,database.config['TEST_STORE_ID'])
    category=db.session.scalar(select(Category))
    piece=Product(store_id=store.id,category_id=category.id,name='Saved location ring',
                  metal='Gold',purity=1,weight=1,making=0,fixed=0,status='published')
    db.session.add(piece)
    db.session.commit()
    path=f'/saved?ids={piece.id}'
    assert 'Saved location ring' in c.get(path).text
    assert ' km · ' not in c.get(path).text
    local=c.get(path+f'&lat={store.latitude}&lon={store.longitude}').text
    assert '0.0 km' in local
    distant=c.get(path+'&lat=0&lon=0').text
    assert 'Saved location ring' in distant and ' km' in distant


def test_custom_purity_and_percentage_making(database):
    import uuid
    from app.models import Category, Product
    from app.services.catalogue import catalogue

    client = database.test_client()
    login(client, database.config["TEST_OWNER_ID"])
    category = db.session.scalar(select(Category))
    data = {
        "mutation": str(uuid.uuid4()),
        "category_id": str(category.id),
        "name": "Custom silver ring",
        "metal": "Silver",
        "purity": "custom",
        "custom_purity": "98.125",
        "weight": "100",
        "making_percentage": "10",
        "fixed": "0",
    }
    blank = dict(data, mutation=str(uuid.uuid4()), name="Silver ring without making", making_percentage="")
    assert client.post("/merchant/products/new", data=blank).status_code == 302
    no_making = db.session.scalar(select(Product).where(Product.name == blank["name"]))
    assert no_making.making_percentage is None and no_making.making == 0
    assert client.post("/merchant/products/new", data=data).status_code == 302
    product = db.session.scalar(select(Product).where(Product.name == data["name"]))
    assert product.purity == Decimal(".98125")
    assert product.making_percentage == 10
    edit = client.get(f"/merchant/products/{product.id}/edit").text
    assert 'value="custom" selected' in edit
    assert 'value="98.12500000"' in edit

    product.status = "published"
    db.session.commit()
    rows, _, _ = catalogue({"ids": str(product.id)})
    assert rows[0][1] == Decimal("10812.50")
    detail = client.get(f"/products/{product.id}").text
    assert "Rs. 10,812.50" in detail
    assert "Making weight (10%)" in detail

    blank_edit = dict(data, mutation=str(uuid.uuid4()), making_percentage="")
    assert client.post(f"/merchant/products/{product.id}/edit", data=blank_edit).status_code == 302
    db.session.refresh(product)
    assert product.making_percentage is None and product.making == 0
    assert "Making weight" not in client.get(f"/products/{product.id}").text
    rows, _, _ = catalogue({"ids": str(product.id)})
    assert rows[0][1] == Decimal("9812.50")


def test_reel_views_deduplicate_and_credit_following_week(database, monkeypatch):
    import uuid
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from app.models import Category, Media, Product, ReelView
    from app.services.core import NEPAL, reel_bonus_hours, reel_week

    database.config["REEL_VIEWS_PER_BONUS_HOUR"] = 1
    last_week = datetime(2026, 11, 11, 12, tzinfo=NEPAL)
    this_week = last_week + timedelta(days=7)
    monkeypatch.setattr("app.routes.now", lambda: last_week)
    monkeypatch.setattr("app.services.core.now", lambda: this_week)
    store = db.session.get(Store, database.config["TEST_STORE_ID"])
    category = db.session.scalar(select(Category))
    product = Product(store_id=store.id, category_id=category.id, name="Reel ring",
                      metal="Gold", purity=1, weight=1, status="published")
    db.session.add(product)
    db.session.flush()
    media = Media(product_id=product.id, store_id=store.id, kind="reel", status="ready", source="test.mp4")
    db.session.add(media)
    db.session.commit()
    url = f"/reels/{media.id}/view"
    client = database.test_client()
    assert client.post(url).status_code == 204
    login(client, store.owner_id)
    assert client.post(url).status_code == 204
    assert db.session.scalar(select(func.count()).select_from(ReelView)) == 0
    login(client, database.config["TEST_ADMIN_ID"])
    assert url in client.get("/reels").text
    assert client.post(url).status_code == 204
    assert client.post(url).status_code == 204
    assert db.session.scalar(select(func.count()).select_from(ReelView)) == 1
    assert reel_bonus_hours(store, reel_week(this_week)) == 1
    assert reel_bonus_hours(store, reel_week(this_week + timedelta(days=7))) == 0
    start = this_week + timedelta(hours=1)
    login(client, store.owner_id)
    response = client.post("/merchant/featured", data={
        "mutation": str(uuid.uuid4()),
        "product_id": str(product.id),
        "start": start.isoformat(),
        "end": (start + timedelta(hours=21)).isoformat(),
    })
    assert response.status_code == 302
