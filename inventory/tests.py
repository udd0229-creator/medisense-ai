from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import BatchForm
from .models import Batch, Category, Medicine, Sale, Supplier
from .services import InsufficientStock, sell_fefo


def make_medicine(name="Paracetamol 500mg"):
    cat = Category.objects.get_or_create(name="Analgesic")[0]
    sup = Supplier.objects.get_or_create(name="Test Supplier", lead_time_days=5)[0]
    return Medicine.objects.create(name=name, category=cat, mrp=20, default_supplier=sup)


def make_batch(med, no, days_to_expiry, qty, price=10):
    today = date.today()
    return Batch.objects.create(
        medicine=med, supplier=med.default_supplier, batch_no=no,
        mfg_date=today - timedelta(days=200), expiry_date=today + timedelta(days=days_to_expiry),
        received_date=today - timedelta(days=30), quantity_received=qty, quantity=qty,
        purchase_price=price)


class FefoSaleTests(TestCase):
    def setUp(self):
        self.med = make_medicine()
        self.late = make_batch(self.med, "B-LATE", 300, 50)
        self.early = make_batch(self.med, "B-EARLY", 60, 10)
        self.expired = make_batch(self.med, "B-EXP", -5, 40)

    def test_sale_uses_earliest_expiry_first(self):              # TC-S1
        rows = sell_fefo(self.med, 8)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].batch, self.early)
        self.early.refresh_from_db()
        self.assertEqual(self.early.quantity, 2)

    def test_sale_spans_two_batches(self):                       # TC-S2
        rows = sell_fefo(self.med, 15)
        self.assertEqual([r.batch.batch_no for r in rows], ["B-EARLY", "B-LATE"])
        self.assertEqual([r.quantity for r in rows], [10, 5])
        self.assertEqual(rows[0].invoice_no, rows[1].invoice_no)

    def test_expired_batch_never_sold(self):                     # TC-S3
        sell_fefo(self.med, 60)
        self.expired.refresh_from_db()
        self.assertEqual(self.expired.quantity, 40)

    def test_insufficient_stock_rolls_back(self):                # TC-S4
        with self.assertRaises(InsufficientStock):
            sell_fefo(self.med, 61)   # only 60 usable units
        self.early.refresh_from_db()
        self.assertEqual(self.early.quantity, 10)
        self.assertEqual(Sale.objects.count(), 0)

    def test_usable_stock_excludes_expired(self):                # TC-S5
        self.assertEqual(self.med.usable_stock, 60)
        self.assertEqual(self.med.total_stock, 100)


class BatchFormTests(TestCase):
    def setUp(self):
        self.med = make_medicine()

    def form(self, **over):
        data = {"medicine": self.med.pk, "supplier": self.med.default_supplier.pk,
                "batch_no": "X1", "mfg_date": date.today() - timedelta(days=10),
                "expiry_date": date.today() + timedelta(days=400), "received_date": date.today(),
                "quantity_received": 100, "quantity": "", "purchase_price": 12}
        data.update(over)
        return BatchForm(data)

    def test_valid_batch_defaults_quantity(self):                # TC-B1
        f = self.form()
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.save().quantity, 100)

    def test_expiry_before_mfg_rejected(self):                   # TC-B2
        f = self.form(expiry_date=date.today() - timedelta(days=20))
        self.assertFalse(f.is_valid())
        self.assertIn("expiry_date", f.errors)

    def test_future_mfg_rejected(self):                          # TC-B3
        self.assertFalse(self.form(mfg_date=date.today() + timedelta(days=5)).is_valid())

    def test_quantity_over_received_rejected(self):              # TC-B4
        self.assertFalse(self.form(quantity=150).is_valid())


class ViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff", password="pass12345")
        self.med = make_medicine()
        make_batch(self.med, "V1", 200, 30)

    def test_login_required(self):                               # TC-V1
        r = self.client.get(reverse("dashboard"))
        self.assertRedirects(r, reverse("login") + "?next=/")

    def test_pages_load_for_logged_in_user(self):                # TC-V2
        self.client.login(username="staff", password="pass12345")
        for name in ["dashboard", "medicine_list", "batch_list", "supplier_list",
                     "sale_create", "sale_list", "reports"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(
            reverse("medicine_detail", args=[self.med.pk])).status_code, 200)

    def test_sale_form_creates_sale(self):                       # TC-V3
        self.client.login(username="staff", password="pass12345")
        r = self.client.post(reverse("sale_create"),
                             {"medicine": self.med.pk, "quantity": 5, "discount_percent": 0})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Sale.objects.get().quantity, 5)

    def test_sale_form_rejects_excess(self):                     # TC-V4
        self.client.login(username="staff", password="pass12345")
        r = self.client.post(reverse("sale_create"),
                             {"medicine": self.med.pk, "quantity": 500, "discount_percent": 0})
        self.assertContains(r, "usable stock")
        self.assertEqual(Sale.objects.count(), 0)
