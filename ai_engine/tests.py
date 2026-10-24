import math
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import Batch, Category, Medicine, Sale, Supplier

from .features import derive
from .forecast import forecast_medicine
from .reorder import compute_reorder
from .risk_model import predict_batches, recommend, risk_level, train_model

TMP = Path(tempfile.mkdtemp())


@override_settings(ML_MODEL_DIR=TMP / "models", DATASET_DIR=TMP / "data")
class AITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.metrics = train_model(n_samples=1500)
        cat = Category.objects.create(name="Analgesic")
        sup = Supplier.objects.create(name="S1", lead_time_days=4, accepts_returns=True)
        cls.fast = Medicine.objects.create(name="Fast", category=cat, mrp=20, default_supplier=sup)
        cls.slow = Medicine.objects.create(name="Slow", category=cat, mrp=50, default_supplier=sup)
        today = date.today()

        def batch(med, no, days, qty):
            return Batch.objects.create(
                medicine=med, supplier=sup, batch_no=no, mfg_date=today - timedelta(days=100),
                expiry_date=today + timedelta(days=days), received_date=today - timedelta(days=60),
                quantity_received=qty, quantity=qty, purchase_price=10)

        cls.fast_batch = batch(cls.fast, "F1", 60, 100)       # sells 10/day -> safe
        cls.slow_batch = batch(cls.slow, "S1", 60, 300)       # sells 0.5/day -> risky
        cls.exp_batch = batch(cls.slow, "S0", -3, 5)
        for i in range(1, 61):
            d = today - timedelta(days=i)
            Sale.objects.create(medicine=cls.fast, batch=cls.fast_batch, quantity=10,
                                unit_price=20, sale_date=d)
            if i % 2 == 0:
                Sale.objects.create(medicine=cls.slow, batch=cls.slow_batch, quantity=1,
                                    unit_price=50, sale_date=d)

    def test_model_accuracy_reasonable(self):                    # TC-A1
        self.assertGreater(self.metrics["accuracy"], 0.8)
        self.assertGreater(self.metrics["roc_auc"], 0.85)

    def test_feature_derivation(self):                           # TC-A2
        f = derive(days_to_expiry=50, quantity=100, qty_ahead=0, avg_daily_sales=1,
                   sales_trend=1, unit_price=10)
        self.assertEqual(f["days_of_stock"], 100)
        self.assertEqual(f["coverage_ratio"], 2.0)

    def test_risk_levels(self):                                  # TC-A3
        self.assertEqual(risk_level(0.85), "High")
        self.assertEqual(risk_level(0.5), "Medium")
        self.assertEqual(risk_level(0.1), "Low")

    def test_slow_batch_high_fast_batch_low(self):               # TC-A4
        res = {r["batch"].batch_no: r for r in predict_batches()}
        self.assertEqual(res["S1"]["level"], "High")
        self.assertEqual(res["F1"]["level"], "Low")
        self.assertEqual(res["S0"]["level"], "Expired")
        self.assertGreater(res["S1"]["expected_loss"], 0)

    def test_recommendation_return_to_supplier(self):            # TC-A5
        self.assertIn("Return to supplier", recommend("High", 30, True, 3))
        self.assertIn("No action", recommend("Low", 300, True, 0.2))

    def test_forecast_close_to_actual_rate(self):                # TC-A6
        fc = forecast_medicine(self.fast)
        self.assertAlmostEqual(fc["daily_mean"], 10, delta=2)
        self.assertEqual(len(fc["forecast"]), 30)

    def test_reorder_formulas(self):                             # TC-A7
        r = compute_reorder(self.fast)
        d = r["daily_demand"]
        self.assertAlmostEqual(r["eoq"], math.ceil(math.sqrt(2 * d * 365 * 200 / (10 * 0.2))),
                               delta=2)
        self.assertGreaterEqual(r["reorder_point"], math.floor(d * 4))
        self.assertLessEqual(r["order_qty"], r["shelf_cap"] + 1)

    def test_ai_pages_load(self):                                # TC-A8
        User.objects.create_user("u", password="pass12345", is_staff=True)
        self.client.login(username="u", password="pass12345")
        for name in ["expiry_risk", "forecast", "reorder", "model_info",
                     "expiry_risk_csv", "reorder_csv"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
