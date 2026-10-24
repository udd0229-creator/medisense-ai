"""
Inventory optimisation: safety stock, reorder point and order quantity.

  d   = forecast average daily demand (units/day)
  sd  = standard deviation of daily demand (last 60 days)
  L   = supplier lead time (days)
  z   = service level factor (1.65 for 95%)

  Safety stock       SS  = z * sd * sqrt(L)
  Reorder point      ROP = d * L + SS
  Annual demand      D   = d * 365
  Economic Order Qty EOQ = sqrt(2 * D * S / H)
        S = ordering cost per order, H = holding cost per unit per year
  Shelf-life cap     CAP = d * shelf_life_days * 0.8
        (never order more than can be sold in 80% of the shelf life)

  Recommended order = min(max(EOQ, ROP - stock + d*L), CAP) when stock <= ROP
"""
import math

from django.conf import settings
from django.db.models import Avg

from .forecast import forecast_medicine


def compute_reorder(medicine, fc=None):
    cfg = settings.MEDISENSE
    fc = fc or forecast_medicine(medicine)
    d = max(fc["daily_mean"], 0.0)
    sd = fc["daily_std"] if fc["daily_std"] == fc["daily_std"] else 0.0  # NaN check
    supplier = medicine.default_supplier
    L = supplier.lead_time_days if supplier else cfg["DEFAULT_LEAD_TIME"]

    avg_cost = medicine.batches.aggregate(a=Avg("purchase_price"))["a"]
    unit_cost = float(avg_cost) if avg_cost else float(medicine.mrp) * 0.75
    H = max(unit_cost * cfg["HOLDING_RATE"], 0.01)
    S = cfg["ORDERING_COST"]

    safety = cfg["SERVICE_LEVEL_Z"] * sd * math.sqrt(L)
    rop = d * L + safety
    annual = d * 365
    eoq = math.sqrt(2 * annual * S / H) if annual > 0 else 0
    cap = d * medicine.shelf_life_days * cfg["SHELF_LIFE_USE_FRACTION"]
    stock = medicine.usable_stock

    if d == 0:
        status, qty = ("No demand", 0)
    elif stock <= rop:
        qty = min(max(eoq, rop - stock + d * L), cap)
        status = "Order now"
    elif stock > cap:
        status, qty = ("Overstocked", 0)
    else:
        status, qty = ("Sufficient", 0)

    days_cover = stock / d if d > 0 else None
    return {
        "medicine": medicine, "stock": stock, "daily_demand": round(d, 2),
        "demand_30": round(fc["total"]), "lead_time": L,
        "safety_stock": math.ceil(safety), "reorder_point": math.ceil(rop),
        "eoq": math.ceil(eoq), "shelf_cap": math.floor(cap),
        "order_qty": math.ceil(qty), "status": status,
        "days_cover": round(days_cover) if days_cover is not None else None,
        "order_cost": round(math.ceil(qty) * unit_cost, 2), "method": fc["method"],
    }


def reorder_table(medicines):
    order = {"Order now": 0, "Overstocked": 1, "Sufficient": 2, "No demand": 3}
    rows = [compute_reorder(m) for m in medicines]
    rows.sort(key=lambda r: (order[r["status"]], r["medicine"].name))
    return rows
