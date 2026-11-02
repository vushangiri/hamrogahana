import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal as D

import pytest
from PIL import Image
from sqlalchemy import select, text

from app.extensions import db
from app.models import Category, Media, Product, Store, User, now
from app.services.catalogue import catalogue
from app.services.core import locked_store, schedule, set_plan

pytestmark = pytest.mark.integration


def auth(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True


def token(**kwargs):
    return {"mutation": str(uuid.uuid4()), **kwargs}


def product(app, status="published"):
    p = Product(
        store_id=app.config["TEST_STORE_ID"],
        category_id=db.session.scalar(select(Category.id)),
        name="Gold ring",
        description="Handcrafted",
        metal="Gold",
        purity=D(".75"),
        weight=D(2),
        making=D(50),
        fixed=D(25),
        status=status,
        search_text="gold ring handcrafted",
    )
    db.session.add(p)
    db.session.commit()
    return p


def image_file():
    out = io.BytesIO()
    Image.new("RGB", (100, 100), "gold").save(out, "PNG")
    out.seek(0)
    return out


def test_migration_schema_and_spatial(database):
    assert "3." in db.session.scalar(text("SELECT postgis_version()"))
    p = product(database)
    rows, more, page = catalogue({"lat": "27.704", "lon": "85.311", "radius": "1"})
    assert rows[0][0].id == p.id and rows[0][1] == D("15275.00")
    assert not catalogue({"lat": "28.209", "lon": "83.986", "radius": "1"})[0]
    assert (
        db.session.scalar(
            text(
                "SELECT count(*) FROM pg_indexes WHERE schemaname=current_schema() AND indexdef LIKE '%gist%'"
            )
        )
        >= 2
    )


def test_catalogue_filters(database):
    product(database)
    for filters in [
        {"q": "nonexistent"},
        {"metal": "Silver"},
        {"price_min": "999999"},
        {"weight_max": "1"},
    ]:
        assert not catalogue(filters)[0]
    assert catalogue({"q": "handcrafted", "price_max": "16000", "weight_min": "1"})[0]
    assert not catalogue({"q": "%' OR 1=1 --"})[0]


def test_registration_login_and_pending(database):
    c = database.test_client()
    result = c.post(
        "/register",
        data={
            "owner_name": "New Owner",
            "phone": "9800000002",
            "email": "",
            "password": "a secure password",
            "name": "New Store",
            "store_phone": "9800000002",
            "address": "Patan",
            "latitude": "27.67",
            "longitude": "85.32",
            "surplus": "10",
        },
    )
    assert result.status_code == 302
    s = db.session.scalar(select(Store).where(Store.name == "New Store"))
    assert s.verification == "pending"
    assert c.get("/merchant").status_code == 200
    c.post("/logout")
    assert c.post("/login", data={"phone": "9800000002", "password": "wrong"}).status_code == 401
    assert (
        c.post("/login", data={"phone": "9800000002", "password": "a secure password"}).status_code
        == 302
    )


def test_owner_publish_upload_and_restriction(database):
    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    p = product(database, "draft")
    assert c.post(f"/merchant/products/{p.id}/publish", data=token()).status_code == 400
    assert (
        c.post(
            f"/merchant/products/{p.id}/media",
            data=token(kind="image", file=(image_file(), "photo.png")),
        ).status_code
        == 302
    )
    assert c.post(f"/merchant/products/{p.id}/publish", data=token()).status_code == 302
    db.session.refresh(p)
    assert p.status == "published"
    admin = database.test_client()
    auth(admin, database.config["TEST_ADMIN_ID"])
    assert (
        admin.post(
            f"/admin/products/{p.id}", data=token(status="archived", reason="Review")
        ).status_code
        == 302
    )
    assert c.post(f"/merchant/products/{p.id}/publish", data=token()).status_code == 400
    assert c.get(f"/products/{p.id}").status_code == 404


def test_cross_owner_and_admin_boundaries(database):
    p = product(database)
    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    assert c.post("/admin/rates", data=token(Gold="1", Silver="1", reason="bad")).status_code == 403
    other = User(name="Other", phone="+9779800000009", password_hash="unused")
    db.session.add(other)
    db.session.commit()
    auth(c, other.id)
    assert c.post(f"/merchant/products/{p.id}/publish", data=token()).status_code == 403


def test_admin_rate_update_and_immutable_audit(database):
    product(database)
    c = database.test_client()
    auth(c, database.config["TEST_ADMIN_ID"])
    payload = token(Gold="20000", Silver="200", reason="Daily update")
    assert c.post("/admin/rates", data=payload).status_code == 302
    assert catalogue({})[0][0][1] == D("30275.00")
    assert c.post("/admin/rates", data=payload).status_code == 409
    with pytest.raises(Exception):
        db.session.execute(text("UPDATE audit SET action='tamper'"))
        db.session.commit()
    db.session.rollback()


def test_feature_overlap_and_quota(database):
    p = product(database)
    s = db.session.get(Store, p.store_id)
    start = now() + timedelta(hours=1)
    with database.test_request_context():
        schedule(s, p, start, start + timedelta(hours=10))
        db.session.commit()
        with pytest.raises(ValueError):
            schedule(s, p, start, start + timedelta(hours=1))
        db.session.rollback()
        with pytest.raises(ValueError):
            schedule(s, p, start + timedelta(hours=11), start + timedelta(hours=22))
        db.session.rollback()


def test_downgrade_hides_excess(database):
    for i in range(22):
        product(database)
    s = locked_store(database.config["TEST_STORE_ID"])
    with database.test_request_context():
        set_plan(s, "Free")
        db.session.commit()
    assert len(db.session.scalars(select(Product).where(Product.status == "excess")).all()) == 2


def test_concurrent_feature_same_product(database):
    p = product(database)
    pid = p.id
    sid = p.store_id
    start = now() + timedelta(hours=1)

    def attempt(_):
        with database.app_context(), database.test_request_context():
            try:
                schedule(
                    db.session.get(Store, sid),
                    db.session.get(Product, pid),
                    start,
                    start + timedelta(hours=2),
                )
                db.session.commit()
                return True
            except ValueError:
                db.session.rollback()
                return False

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, range(2)))
    assert sum(results) == 1


def test_store_suspension_hides_media(database):
    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    p = product(database, "draft")
    c.post(
        f"/merchant/products/{p.id}/media",
        data=token(kind="image", file=(image_file(), "photo.png")),
    )
    c.post(f"/merchant/products/{p.id}/publish", data=token())
    m = db.session.scalar(select(Media).where(Media.product_id == p.id))
    guest = database.test_client()
    assert guest.get(f"/media/{m.id}/640").status_code == 200
    admin = database.test_client()
    auth(admin, database.config["TEST_ADMIN_ID"])
    admin.post(f"/admin/stores/{p.store_id}", data=token(action="suspend", reason="Review"))
    assert guest.get(f"/media/{m.id}/640").status_code == 404
    assert not catalogue({})[0]


def test_all_dashboard_tabs(database):
    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    for tab in ["Overview", "Products", "Media", "Featured", "Store", "Subscription"]:
        assert c.get("/merchant?tab=" + tab).status_code == 200
    auth(c, database.config["TEST_ADMIN_ID"])
    for tab in [
        "Overview",
        "Stores",
        "Products",
        "Reels",
        "Rates",
        "Units",
        "Plans",
        "Featured",
        "Banners",
        "Audit",
    ]:
        assert c.get("/admin?tab=" + tab).status_code == 200


def test_store_catalogue_search_pagination_and_visibility(database):
    for i in range(14):
        p = product(database)
        p.name = f"Ring {i}"
        p.search_text = f"ring {i} unique{i}"
    hidden = product(database, "draft")
    hidden.name = "Private draft"
    db.session.commit()
    c = database.test_client()
    url = f"/stores/{p.store_id}"
    first = c.get(url)
    assert first.status_code == 200 and b"More pieces" in first.data
    assert b"Private draft" not in first.data
    second = c.get(url + "?page=2&sort=new")
    assert second.status_code == 200 and b"Previous" in second.data
    assert b"More pieces" not in second.data
    match = c.get(url + "?q=unique13&lat=-80&lon=-170&radius=.1")
    assert b"Ring 13" in match.data and b"Ring 12" not in match.data
    assert b"No matching jewellery" in c.get(url + "?q=absent").data
    assert b"Ring 13" not in c.get(url + f"?store={uuid.uuid4()}").data
    store = db.session.get(Store, p.store_id)
    store.active = False
    db.session.commit()
    assert c.get(url).status_code == 404


def test_admin_detail_views_and_access(database):
    p = product(database, "archived")
    p.description = "Private archived description"
    db.session.commit()
    c = database.test_client()
    store_url, product_url = f"/admin/stores/{p.store_id}", f"/admin/products/{p.id}"
    assert c.get(store_url).status_code == 403
    assert c.get(product_url).status_code == 403
    auth(c, database.config["TEST_OWNER_ID"])
    assert c.get(store_url).status_code == 403
    assert c.get(product_url).status_code == 403
    auth(c, database.config["TEST_ADMIN_ID"])
    response = c.get(store_url)
    assert response.status_code == 200
    assert b"Owner details" in response.data and product_url.encode() in response.data
    response = c.get(product_url)
    assert response.status_code == 200
    assert b"Private archived description" in response.data and b"Archived" in response.data
    assert b"password_hash" not in response.data


def test_media_preview_and_inline_evidence(database):
    from app.services.media import upload

    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    p = product(database)
    c.post(f"/merchant/products/{p.id}/media", data=token(kind="image", file=(image_file(), "photo.png")))
    m = db.session.scalar(select(Media).where(Media.product_id == p.id))
    guest = database.test_client()
    preview_url = f"/media/{m.id}/preview"
    assert guest.get(preview_url).status_code == 200
    response = guest.get(f"/media/{m.id}/file")
    assert response.mimetype == "image/webp"
    assert response.headers["Content-Disposition"].startswith("inline")
    with database.test_request_context():
        from werkzeug.datastructures import FileStorage

        evidence = upload(FileStorage(stream=image_file(), filename="evidence.png"), p.store, "payment")
        db.session.commit()
    assert guest.get(f"/media/{evidence.id}/preview").status_code == 404
    assert c.get(f"/media/{evidence.id}/preview").status_code == 200
    response = c.get(f"/media/{evidence.id}/file")
    assert response.headers["Content-Disposition"].startswith("inline")
    p.status = "suspended"
    db.session.commit()
    assert guest.get(preview_url).status_code == 404
    assert c.get(preview_url).status_code == 200


def test_uploaded_reel_worker_and_inline_playback(database, tmp_path):
    import subprocess

    from app.models import Job
    from app.services.media import path_for, process_one

    source = tmp_path / "landscape.mov"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         "color=c=gold:s=320x180:r=5", "-t", "5", "-c:v", "mpeg4", "-threads", "1", str(source)],
        check=True,
    )
    p = product(database)
    c = database.test_client()
    auth(c, database.config["TEST_OWNER_ID"])
    with source.open("rb") as file:
        response = c.post(f"/merchant/products/{p.id}/media", data=token(kind="reel", file=(file, "clip.mov")))
    assert response.status_code == 302
    media = db.session.scalar(select(Media).where(Media.product_id == p.id, Media.kind == "reel"))
    assert media.status == "queued"
    source_key = media.source
    assert database.test_client().get(f"/media/{media.id}/preview").status_code == 404
    assert process_one()
    db.session.refresh(media)
    assert media.status == "ready"
    assert db.session.scalar(select(Job).where(Job.media_id == media.id)).state == "done"
    assert not path_for(source_key).exists()
    guest = database.test_client()
    preview = guest.get(f"/media/{media.id}/preview")
    assert preview.status_code == 200 and b"<video" in preview.data
    response = guest.get(f"/media/{media.id}/file", headers={"Range": "bytes=0-99"})
    assert response.status_code == 206
    assert response.mimetype == "video/mp4"
    assert response.headers["Content-Disposition"].startswith("inline")
    assert guest.get(f"/media/{media.id}/thumb").mimetype == "image/webp"
