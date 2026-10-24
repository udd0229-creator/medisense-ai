"""
Database models for MediSense AI.

Tables: Category, Supplier, Medicine, Batch, Sale
"""
from datetime import date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    contact_person = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    lead_time_days = models.PositiveIntegerField(
        default=7, help_text="Average days between placing an order and receiving it"
    )
    accepts_returns = models.BooleanField(
        default=True, help_text="Supplier accepts return of near-expiry stock"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Medicine(models.Model):
    STORAGE_CHOICES = [
        ("ROOM", "Room temperature (below 25°C)"),
        ("COOL", "Cool place (8–15°C)"),
        ("COLD", "Refrigerated (2–8°C)"),
    ]

    name = models.CharField(max_length=120, unique=True)
    generic_name = models.CharField(max_length=120, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="medicines")
    manufacturer = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=30, default="strip", help_text="strip, bottle, vial, tube...")
    mrp = models.DecimalField("MRP (Rs.)", max_digits=10, decimal_places=2,
                              validators=[MinValueValidator(0)])
    default_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="medicines")
    shelf_life_days = models.PositiveIntegerField(
        default=540, help_text="Typical shelf life of a new batch at receipt (days)"
    )
    min_stock = models.PositiveIntegerField(default=10, help_text="Manual minimum stock level")
    storage = models.CharField(max_length=4, choices=STORAGE_CHOICES, default="ROOM")
    prescription_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def usable_stock(self):
        """Quantity in non-expired batches."""
        return (self.batches.filter(expiry_date__gt=date.today())
                .aggregate(t=Sum("quantity"))["t"] or 0)

    @property
    def total_stock(self):
        return self.batches.aggregate(t=Sum("quantity"))["t"] or 0


class BatchQuerySet(models.QuerySet):
    def in_stock(self):
        return self.filter(quantity__gt=0)

    def usable(self):
        return self.in_stock().filter(expiry_date__gt=date.today())

    def expired(self):
        return self.in_stock().filter(expiry_date__lte=date.today())

    def fefo(self):
        """First-Expiry-First-Out ordering."""
        return self.order_by("expiry_date", "received_date", "id")


class Batch(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="batches")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="batches")
    batch_no = models.CharField(max_length=40)
    mfg_date = models.DateField("Manufacturing date")
    expiry_date = models.DateField()
    received_date = models.DateField(default=date.today)
    quantity_received = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    quantity = models.PositiveIntegerField(help_text="Quantity currently in stock")
    purchase_price = models.DecimalField("Purchase price per unit (Rs.)", max_digits=10,
                                         decimal_places=2, validators=[MinValueValidator(0)])

    objects = BatchQuerySet.as_manager()

    class Meta:
        ordering = ["expiry_date"]
        unique_together = ("medicine", "batch_no")
        verbose_name_plural = "batches"

    def __str__(self):
        return f"{self.medicine.name} - {self.batch_no}"

    @property
    def days_to_expiry(self):
        return (self.expiry_date - date.today()).days

    @property
    def is_expired(self):
        return self.expiry_date <= date.today()

    @property
    def stock_value(self):
        return float(self.purchase_price) * self.quantity


class Sale(models.Model):
    """One row per batch used. A single customer sale of 10 units may create
    two Sale rows if FEFO takes 6 units from one batch and 4 from the next."""
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT, related_name="sales")
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="sales")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sale_date = models.DateField(default=date.today)
    invoice_no = models.CharField(max_length=30, blank=True)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                null=True, blank=True)

    class Meta:
        ordering = ["-sale_date", "-id"]

    def __str__(self):
        return f"{self.sale_date} {self.medicine.name} x{self.quantity}"

    @property
    def amount(self):
        return float(self.unit_price) * self.quantity * (1 - float(self.discount_percent) / 100)
