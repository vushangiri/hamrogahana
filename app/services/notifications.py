"""Persist role-specific inbox messages in the triggering transaction."""
from sqlalchemy import select

from ..extensions import db
from ..models import Notification, Product, Store, Upgrade, User


def notify_event(action, entity, detail):
    if action in ("upgrade.requested", "store.registered"):
        message = "A store has requested a plan upgrade." if action == "upgrade.requested" else "A new store is awaiting verification."
        for uid in db.session.scalars(select(User.id).where(User.role == "admin")):
            db.session.add(Notification(user_id=uid, message=message, href="/admin?tab=Plans" if action == "upgrade.requested" else "/admin"))
    sid = None
    if action in ("store.status", "subscription.changed"):
        sid = entity
    elif action == "upgrade.reviewed":
        item = db.session.get(Upgrade, entity)
        sid = item.store_id if item else None
    elif action == "product.admin_status":
        item = db.session.get(Product, entity)
        sid = item.store_id if item else None
    if sid:
        store = db.session.get(Store, sid)
        if store:
            messages = {
                "store.status": f"Your store status is now {detail.get('new', '')}. {detail.get('reason', '')}",
                "subscription.changed": f"Your subscription has changed. {detail.get('new', '')}",
                "upgrade.reviewed": f"Your upgrade request was {detail.get('status', '')}.",
                "product.admin_status": f"A product was marked {detail.get('new', '')}. {detail.get('reason', '')}",
            }
            db.session.add(Notification(user_id=store.owner_id, message=messages[action][:500], href="/merchant"))
