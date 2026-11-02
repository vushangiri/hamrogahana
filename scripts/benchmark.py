"""Read-only catalogue timing against an operator-prepared representative database.

Run: python scripts/benchmark.py --runs 30
Data must already contain representative stores/products. This never invents latency claims.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import func, select

from app import create_app
from app.extensions import db
from app.models import Product, Store
from app.services.catalogue import catalogue

parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=int, default=30)
args = parser.parse_args()
app = create_app()
with app.app_context():
    result = {
        "products": db.session.scalar(select(func.count()).select_from(Product)),
        "stores": db.session.scalar(select(func.count()).select_from(Store)),
        "runs": args.runs,
        "milliseconds": {},
    }
    for name, filters in [
        ("nearby", {"radius": "10"}),
        ("gold", {"metal": "Gold", "radius": "50"}),
        ("price", {"sort": "low", "price_max": "1000000"}),
        ("text", {"q": "gold"}),
    ]:
        timings = []
        for _ in range(args.runs):
            db.session.expire_all()
            start = time.perf_counter()
            rows, _, _ = catalogue(filters)
            timings.append((time.perf_counter() - start) * 1000)
        ordered = sorted(timings)
        result["milliseconds"][name] = {
            "median": round(statistics.median(ordered), 2),
            "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
            "last_rows": len(rows),
        }
    print(json.dumps(result, indent=2))
