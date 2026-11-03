import re
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import Audit, Notification, PasswordReset, User


def auth(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True


def details(phone="9800000001"):
    return dict(name="Owner", store_name="Test Jeweller", phone=phone, address="Kathmandu")


def test_request_deduplication_and_approval(database):
    c = database.test_client()
    assert c.get("/forgot-password").status_code == 200
    assert c.post("/forgot-password", data=details()).status_code == 200
    assert c.post("/forgot-password", data=details("+9779800000001")).status_code == 200
    assert db.session.scalar(select(func.count()).select_from(PasswordReset)) == 1
    assert db.session.scalar(select(func.count()).select_from(Notification).where(Notification.href == "/admin/password-resets")) == 1
    item = db.session.scalar(select(PasswordReset))
    rid = item.id
    url = f"/admin/password-resets/{rid}"
    assert c.get("/admin/password-resets").status_code == 403
    auth(c, database.config["TEST_OWNER_ID"])
    assert c.post(url, data={"action":"approved", "mutation":str(uuid.uuid4())}).status_code == 403
    auth(c, database.config["TEST_ADMIN_ID"])
    assert b"Registered details" in c.get("/admin/password-resets").data
    response = c.post(url, data={"action":"approved", "mutation":str(uuid.uuid4())})
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    password = re.search(rb'id="generatedPassword">([^<]+)', response.data).group(1).decode()
    user = db.session.get(User,database.config["TEST_OWNER_ID"])
    assert check_password_hash(user.password_hash, password)
    assert not check_password_hash(user.password_hash,"testpassword123")
    assert password not in c.get("/admin/password-resets").text
    assert all(password not in str(a.detail) for a in db.session.scalars(select(Audit)))
    assert c.post(url, data={"action":"approved", "mutation":str(uuid.uuid4())}).status_code == 400
    c.post("/logout")
    assert c.post("/login", data={"phone":user.phone,"password":password}).status_code == 302
    assert c.post("/forgot-password", data=details()).status_code == 200
    assert db.session.scalar(select(func.count()).select_from(PasswordReset)) == 2


def test_reject_and_unknown_account(database):
    c = database.test_client()
    for number in ("9800000001","9800000099"):
        assert c.post("/forgot-password",data=details(number)).status_code == 200
    original=db.session.get(User,database.config["TEST_OWNER_ID"]).password_hash
    auth(c,database.config["TEST_ADMIN_ID"])
    for item in db.session.scalars(select(PasswordReset)).all():
        url=f"/admin/password-resets/{item.id}"
        if item.phone.endswith("99"):
            assert c.post(url,data={"action":"approved","mutation":str(uuid.uuid4())}).status_code == 400
        assert c.post(url,data={"action":"rejected","mutation":str(uuid.uuid4())}).status_code == 302
    assert db.session.get(User,database.config["TEST_OWNER_ID"]).password_hash == original


def test_simultaneous_requests(database):
    def submit(_):
        with database.test_client() as c:
            return c.post("/forgot-password",data=details()).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(submit, range(2))) == [200,200]
    assert db.session.scalar(select(func.count()).select_from(PasswordReset)) == 1


def test_six_character_registration(database):
    c=database.test_client()
    data=dict(owner_name="New Owner",phone="9800000022",password="12345",name="New Store",store_phone="9800000022",address="Kathmandu",latitude="27.704",longitude="85.311",surplus="0")
    assert c.post("/register",data=data).status_code == 400
    data["password"]="123456"
    assert c.post("/register",data=data).status_code == 302
    assert check_password_hash(db.session.scalar(select(User).where(User.phone=="+9779800000022")).password_hash,"123456")


def test_admin_cli_accepts_six_characters(database, monkeypatch):
    monkeypatch.setattr("app.cli.getpass.getpass",lambda prompt:"123456")
    result=database.test_cli_runner().invoke(args=["create-admin","--phone-number","9800000033","--name","New Admin"])
    assert result.exit_code == 0, result.output
    user=db.session.scalar(select(User).where(User.phone=="+9779800000033"))
    assert user.role == "admin" and check_password_hash(user.password_hash,"123456")
