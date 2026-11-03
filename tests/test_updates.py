from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Notification, Rate, RateSync, Store
from app.services.core import NEPAL
from app.services.rates import parse_rates, sync_rates


def feed(day="2026-11-03"):
    return [dict(rateType=label, todayDate=f"{day}T04:50:07+00:00", todayBaseRatePerGram=value) for label, value in [("छापावाल सुन (१० ग्राम)",235770),("छापावाल सुन (१ तोला)",275000),("असली चाँदी दर (१० ग्राम)",3151),("असली चाँदी दर (१ तोला)",3675)]]


def test_feed_units_and_dates():
    day = datetime(2026,11,3).date()
    assert parse_rates(feed(),day)["Gold"]["ten"] / 10 == Decimal("23577")
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
    assert gold.value==Decimal("23577") and gold.per_tola==Decimal("275000")
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
    assert db.session.get(Rate,"Silver").value == Decimal("315.1")
