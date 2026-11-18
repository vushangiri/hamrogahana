import uuid
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models import DisplaySettings, Unit
from test_integration import auth, product, token


def test_default_and_visitor_unit_conversions(database):
    unit=db.session.scalar(select(Unit).where(Unit.name=="Tola"))
    db.session.commit()
    uid=unit.id
    p=product(database)
    pid=p.id
    c=database.test_client()
    auth(c,database.config["TEST_OWNER_ID"])
    assert c.post("/admin/units/default",data=token(unit=str(uid))).status_code==403
    auth(c,database.config["TEST_ADMIN_ID"])
    assert c.post("/admin/units/default",data=token(unit=str(uid))).status_code==302
    assert db.session.get(DisplaySettings,1).default_unit_id==uid
    c.post("/logout")
    html=c.get("/").text
    assert "Pure Gold / tola" in html and "116,638.00" in html
    html=c.get(f"/products/{pid}").text
    assert "0.17 tola" in html and "15,275.00" in html
    assert "Pure rate / tola" in html
    assert c.post("/display-unit",data={"unit":"gram","next":f"/products/{pid}"}).status_code==302
    html=c.get(f"/products/{pid}").text
    assert "2 g" in html and "Pure rate / g" in html and "15,275.00" in html
    assert c.post("/display-unit",data={"unit":"default"}).status_code==302
    assert "Pure Gold / tola" in c.get("/").text
    c.set_cookie("hg-unit",str(uuid.uuid4()))
    assert "Pure Gold / tola" in c.get("/").text
    assert c.post("/display-unit",data={"unit":"nonexistent"}).status_code==400
    result=c.post("/display-unit",data={"unit":"gram","next":"//example.com"})
    assert result.location=="/"


def test_default_unit_cannot_be_disabled(database):
    unit=Unit(name="Custom",symbol="custom",grams=Decimal(".5"))
    db.session.add(unit)
    db.session.commit()
    uid=unit.id
    c=database.test_client()
    auth(c,database.config["TEST_ADMIN_ID"])
    assert c.post("/admin/units/default",data=token(unit=str(uid))).status_code==302
    assert c.post(f"/admin/units/{uid}",data=token(name="Custom",symbol="custom",grams=".5",description="")).status_code==400
    assert db.session.get(Unit,uid).active
    assert c.post("/admin/units/default",data=token(unit="gram")).status_code==302
    assert c.post(f"/admin/units/{uid}",data=token(name="Custom",symbol="custom",grams=".5",description="")).status_code==302
    assert c.post("/admin/units/default",data=token(unit=str(uid))).status_code==400
    assert db.session.get(DisplaySettings,1).default_unit_id is None
