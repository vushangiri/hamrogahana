"""Daily FENEGOSIDA import; values in the feed are unit totals, despite field names."""
from datetime import datetime, time
from decimal import Decimal

import requests
from sqlalchemy import select, text

from ..extensions import db
from ..models import Audit, Rate, RateSync, now
from .core import NEPAL, decimal

URL = "https://api.fenegosida.org/api/website/v1/Dashboard/today"


def parse_rates(payload, day):
    if not isinstance(payload, list):
        raise ValueError("Unexpected rate response")
    result = {}
    for row in payload:
        label = row["rateType"]
        metal = "Gold" if "छापावाल सुन" in label else "Silver" if "चाँदी" in label else None
        if not metal:
            continue
        stamp = datetime.fromisoformat(row["todayDate"].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.astimezone(NEPAL).date() != day:
            raise ValueError("Feed rates are not for today in Nepal")
        unit = "ten" if "१० ग्राम" in label else "tola" if "१ तोला" in label else None
        if unit:
            if unit in result.setdefault(metal, {}):
                raise ValueError("Duplicate rate in feed")
            result[metal][unit] = decimal(row["todayBaseRatePerGram"], ".0001", places=4)
    if any(set(result.get(m, {})) != {"ten", "tola"} for m in ("Gold", "Silver")):
        raise ValueError("Feed must contain both units for gold and silver")
    return result


def sync_rates(at=None):
    started = at or now()
    local = started.astimezone(NEPAL)
    if not time(10, 45) <= local.time().replace(tzinfo=None) <= time(11, 15):
        return False
    # A transaction lock prevents duplicate imports across scheduler replicas.
    if not db.session.scalar(text("SELECT pg_try_advisory_xact_lock(748192001)")):
        db.session.rollback()
        return False
    if db.session.get(RateSync, local.date()):
        db.session.rollback()
        return False
    response = requests.get(URL, timeout=(5, 15))
    response.raise_for_status()
    values = parse_rates(response.json(), local.date())
    for metal in ("Gold", "Silver"):
        rate = db.session.scalar(select(Rate).where(Rate.metal == metal).with_for_update().execution_options(populate_existing=True))
        # A manual publish made while the HTTP request was in flight wins.
        if rate and rate.updated_at > started:
            continue
        if rate is None:
            rate = Rate(metal=metal)
            db.session.add(rate)
        previous = rate.value
        rate.value = (values[metal]["ten"] / Decimal(10)).quantize(Decimal(".0001"))
        rate.per_ten_grams, rate.per_tola = values[metal]["ten"], values[metal]["tola"]
        rate.effective_date, rate.source, rate.updated_at = local.date(), "fenegosida", started
        db.session.add(Audit(action="rate.changed", entity_id=metal, detail={"previous": str(previous), "new": str(rate.value), "reason": "FENEGOSIDA daily import", "date": str(local.date())}))
    db.session.add(RateSync(day=local.date(), checked_at=started))
    db.session.commit()
    return True
