"""
Feature engineering shared by training and live prediction.

For every batch the model sees 8 numbers:

  days_to_expiry   days left until the batch expires
  quantity         units of this batch in stock
  qty_ahead        units of the same medicine that will be sold first (FEFO)
  avg_daily_sales  medicine's average units sold per day (last 30 days)
  sales_trend      last-7-day sales rate / last-30-day sales rate
  days_of_stock    (qty_ahead + quantity) / avg_daily_sales
  coverage_ratio   days_of_stock / days_to_expiry  (>1 means stock outlasts expiry)
  unit_price       purchase price per unit
"""
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Sum

FEATURE_COLUMNS = [
    "days_to_expiry", "quantity", "qty_ahead", "avg_daily_sales",
    "sales_trend", "days_of_stock", "coverage_ratio", "unit_price",
]

MIN_RATE = 0.05          # avoid division by zero for medicines with no sales
MAX_DAYS_OF_STOCK = 3650


def derive(days_to_expiry, quantity, qty_ahead, avg_daily_sales, sales_trend, unit_price):
    """Return the full feature dict from the raw values."""
    rate = max(avg_daily_sales, MIN_RATE)
    days_of_stock = min((qty_ahead + quantity) / rate, MAX_DAYS_OF_STOCK)
    coverage = min(days_of_stock / max(days_to_expiry, 1), 20.0)
    return {
        "days_to_expiry": days_to_expiry,
        "quantity": quantity,
        "qty_ahead": qty_ahead,
        "avg_daily_sales": round(avg_daily_sales, 3),
        "sales_trend": round(sales_trend, 3),
        "days_of_stock": round(days_of_stock, 1),
        "coverage_ratio": round(coverage, 3),
        "unit_price": float(unit_price),
    }


def sales_rates(today=None):
    """Return {medicine_id: (rate_30d, trend)} computed from Sale rows."""
    from inventory.models import Sale

    today = today or date.today()
    window = settings.MEDISENSE["SALES_WINDOW_DAYS"]
    start30 = today - timedelta(days=window)
    start7 = today - timedelta(days=7)

    s30 = dict(Sale.objects.filter(sale_date__gt=start30, sale_date__lte=today)
               .values_list("medicine_id").annotate(t=Sum("quantity")))
    s7 = dict(Sale.objects.filter(sale_date__gt=start7, sale_date__lte=today)
              .values_list("medicine_id").annotate(t=Sum("quantity")))
    rates = {}
    for mid in set(s30) | set(s7):
        r30 = (s30.get(mid) or 0) / window
        r7 = (s7.get(mid) or 0) / 7
        trend = (r7 / r30) if r30 > 0 else 1.0
        rates[mid] = (r30, min(trend, 5.0))
    return rates


def batch_features(batches, today=None):
    """Build feature rows for in-stock, non-expired batches.

    `batches` is a queryset/list of Batch objects. Returns a list of
    (batch, feature_dict) tuples.
    """
    from inventory.models import Batch

    today = today or date.today()
    rates = sales_rates(today)

    # Pre-load all usable batches grouped by medicine in FEFO order to find qty_ahead
    usable = (Batch.objects.filter(quantity__gt=0, expiry_date__gt=today)
              .order_by("medicine_id", "expiry_date", "received_date", "id")
              .values_list("id", "medicine_id", "quantity"))
    ahead = {}
    running = {}
    for bid, mid, qty in usable:
        ahead[bid] = running.get(mid, 0)
        running[mid] = running.get(mid, 0) + qty

    rows = []
    for b in batches:
        rate, trend = rates.get(b.medicine_id, (0.0, 1.0))
        feats = derive(
            days_to_expiry=(b.expiry_date - today).days,
            quantity=b.quantity,
            qty_ahead=ahead.get(b.id, 0),
            avg_daily_sales=rate,
            sales_trend=trend,
            unit_price=b.purchase_price,
        )
        rows.append((b, feats))
    return rows
