"""Presentation-only conversions. Canonical pricing and weights stay in grams."""
from decimal import Decimal
from types import SimpleNamespace

from flask import g, request
from sqlalchemy import select

from ..extensions import db
from ..models import DisplaySettings, Unit

GRAM = SimpleNamespace(id="gram", name="Gram", symbol="g", grams=Decimal(1))


def unit_context():
    if "display_units" not in g:
        units = [GRAM, *db.session.scalars(select(Unit).where(Unit.active).order_by(Unit.name)).all()]
        settings = db.session.get(DisplaySettings, 1)
        default = next((u for u in units if settings and str(u.id) == str(settings.default_unit_id)), GRAM)
        selected = next((u for u in units if str(u.id) == request.cookies.get("hg-unit")), default)
        g.display_units = dict(available_units=units, default_unit=default, display_unit=selected)
    return g.display_units


def unit_rate(value):
    return value * unit_context()["display_unit"].grams


def unit_weight(value):
    converted = value / unit_context()["display_unit"].grams
    if 0 < converted < Decimal(".000001"):
        return "<0.000001"
    return format(converted.quantize(Decimal(".000001")).normalize(), "f")
