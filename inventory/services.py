"""
Business logic for stock movement.

sell_fefo() implements First-Expiry-First-Out dispensing: units are always
taken from the non-expired batch that expires first.
"""
from datetime import date

from django.db import transaction
from django.utils.crypto import get_random_string

from .models import Batch, Sale


class InsufficientStock(Exception):
    pass


@transaction.atomic
def sell_fefo(medicine, quantity, unit_price=None, discount_percent=0, user=None,
              sale_date=None, invoice_no=None):
    """Sell `quantity` units of `medicine` using FEFO.

    Returns the list of Sale rows created. Raises InsufficientStock if usable
    (non-expired) stock is not enough. Expired batches are never sold.
    """
    sale_date = sale_date or date.today()
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    batches = list(
        Batch.objects.select_for_update()
        .filter(medicine=medicine, quantity__gt=0, expiry_date__gt=sale_date)
        .fefo()
    )
    available = sum(b.quantity for b in batches)
    if available < quantity:
        raise InsufficientStock(
            f"Only {available} {medicine.unit}(s) of {medicine.name} in usable stock"
        )

    unit_price = medicine.mrp if unit_price is None else unit_price
    invoice_no = invoice_no or "INV-" + get_random_string(6, "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    remaining = quantity
    rows = []
    for batch in batches:
        if remaining == 0:
            break
        take = min(batch.quantity, remaining)
        batch.quantity -= take
        batch.save(update_fields=["quantity"])
        rows.append(Sale.objects.create(
            medicine=medicine, batch=batch, quantity=take, unit_price=unit_price,
            discount_percent=discount_percent, sale_date=sale_date,
            invoice_no=invoice_no, sold_by=user,
        ))
        remaining -= take
    return rows
