import hashlib
import uuid
from datetime import timedelta
from functools import wraps

from flask import abort, request
from flask_login import current_user
from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert

from .extensions import db
from .models import Mutation, Throttle, now


def admin_only(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def throttle(key, limit, seconds):
    key = hashlib.sha256(key.encode()).hexdigest()
    t = now()
    stmt = insert(Throttle).values(key=key, count=1, expires=t + timedelta(seconds=seconds))
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"],
        set_={
            "count": case((Throttle.expires <= t, 1), else_=Throttle.count + 1),
            "expires": case(
                (Throttle.expires <= t, t + timedelta(seconds=seconds)), else_=Throttle.expires
            ),
        },
    ).returning(Throttle.count)
    count = db.session.scalar(stmt)
    db.session.commit()
    if count > limit:
        abort(429, description="Too many requests. Please wait and try again.")


def once():
    """Atomic request token, committed with domain changes; duplicate returns 409."""
    try:
        key = uuid.UUID(request.form.get("mutation", ""))
    except ValueError:
        raise ValueError("Reload this form before submitting") from None
    inserted = db.session.scalar(
        insert(Mutation)
        .values(key=key, actor_id=current_user.id, path=request.path)
        .on_conflict_do_nothing()
        .returning(Mutation.key)
    )
    if not inserted:
        abort(409, description="This form was already submitted. Refresh to see its result.")
