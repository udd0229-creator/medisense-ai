"""
python manage.py seed_data

Creates demo users, categories, suppliers, 36 medicines and ~120 days of
simulated stock receipts and FEFO sales so every screen has realistic data.
"""
import random
from datetime import date, timedelta

import numpy as np
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Batch, Category, Medicine, Sale, Supplier

CATEGORIES = {
    "Analgesic": "Pain relief and fever",
    "Antibiotic": "Bacterial infections",
    "Antihistamine": "Allergy and cold",
    "Antidiabetic": "Blood sugar control",
    "Antacid / GI": "Acidity, digestion, diarrhoea",
    "Cardiac": "Heart and blood pressure",
    "Vitamins & Supplements": "Nutritional supplements",
    "Respiratory": "Cough, asthma",
    "Dermatology": "Skin creams and ointments",
}

SUPPLIERS = [
    ("Patna Pharma Distributors", "R. K. Sinha", 3, True),
    ("Ganga Healthcare Supplies", "Anita Kumari", 5, True),
    ("Magadh Medical Agencies", "S. Prasad", 7, False),
    ("Bihar Life Sciences Traders", "Md. Imran", 10, True),
]

# name, generic, category, unit, mrp, shelf_life_days, daily_rate, storage, rx
MEDICINES = [
    ("Paracetamol 500mg", "Paracetamol", "Analgesic", "strip", 20, 1095, 22, "ROOM", False),
    ("Paracetamol 650mg", "Paracetamol", "Analgesic", "strip", 32, 1095, 14, "ROOM", False),
    ("Ibuprofen 400mg", "Ibuprofen", "Analgesic", "strip", 28, 1095, 6, "ROOM", False),
    ("Diclofenac Gel 30g", "Diclofenac", "Analgesic", "tube", 95, 730, 2.5, "ROOM", False),
    ("Aceclofenac 100mg", "Aceclofenac", "Analgesic", "strip", 60, 730, 0.6, "ROOM", True),
    ("Azithromycin 500mg", "Azithromycin", "Antibiotic", "strip", 120, 730, 4, "ROOM", True),
    ("Amoxicillin 500mg", "Amoxicillin", "Antibiotic", "strip", 85, 730, 5, "ROOM", True),
    ("Cefixime 200mg", "Cefixime", "Antibiotic", "strip", 110, 730, 2, "ROOM", True),
    ("Ciprofloxacin 500mg", "Ciprofloxacin", "Antibiotic", "strip", 60, 1095, 0.5, "ROOM", True),
    ("Doxycycline 100mg", "Doxycycline", "Antibiotic", "strip", 75, 730, 0.4, "ROOM", True),
    ("Cetirizine 10mg", "Cetirizine", "Antihistamine", "strip", 18, 1095, 12, "ROOM", False),
    ("Levocetirizine 5mg", "Levocetirizine", "Antihistamine", "strip", 45, 1095, 6, "ROOM", False),
    ("Montelukast 10mg", "Montelukast", "Antihistamine", "strip", 150, 730, 1.0, "ROOM", True),
    ("Metformin 500mg", "Metformin", "Antidiabetic", "strip", 30, 1095, 10, "ROOM", True),
    ("Glimepiride 2mg", "Glimepiride", "Antidiabetic", "strip", 90, 730, 3, "ROOM", True),
    ("Insulin Glargine 100IU", "Insulin glargine", "Antidiabetic", "vial", 650, 365, 0.5, "COLD", True),
    ("Pantoprazole 40mg", "Pantoprazole", "Antacid / GI", "strip", 95, 730, 11, "ROOM", False),
    ("Omeprazole 20mg", "Omeprazole", "Antacid / GI", "strip", 55, 730, 4, "ROOM", False),
    ("ORS Sachet", "Oral rehydration salts", "Antacid / GI", "sachet", 22, 730, 9, "ROOM", False),
    ("Antacid Syrup 200ml", "Magnesium hydroxide", "Antacid / GI", "bottle", 110, 540, 2, "ROOM", False),
    ("Loperamide 2mg", "Loperamide", "Antacid / GI", "strip", 25, 1095, 0.5, "ROOM", False),
    ("Amlodipine 5mg", "Amlodipine", "Cardiac", "strip", 40, 1095, 8, "ROOM", True),
    ("Telmisartan 40mg", "Telmisartan", "Cardiac", "strip", 85, 730, 6, "ROOM", True),
    ("Atorvastatin 10mg", "Atorvastatin", "Cardiac", "strip", 100, 730, 5, "ROOM", True),
    ("Clopidogrel 75mg", "Clopidogrel", "Cardiac", "strip", 95, 730, 0.8, "ROOM", True),
    ("Vitamin D3 60000IU", "Cholecalciferol", "Vitamins & Supplements", "strip", 120, 730, 3, "ROOM", False),
    ("Vitamin B-Complex", "B-complex", "Vitamins & Supplements", "strip", 35, 540, 5, "ROOM", False),
    ("Calcium + D3 500mg", "Calcium carbonate", "Vitamins & Supplements", "strip", 110, 730, 3, "ROOM", False),
    ("Iron Folic Acid", "Ferrous ascorbate", "Vitamins & Supplements", "strip", 90, 730, 0.7, "ROOM", False),
    ("Multivitamin Syrup 200ml", "Multivitamin", "Vitamins & Supplements", "bottle", 140, 365, 0.6, "COOL", False),
    ("Cough Syrup 100ml", "Dextromethorphan", "Respiratory", "bottle", 115, 540, 7, "ROOM", False),
    ("Salbutamol Inhaler", "Salbutamol", "Respiratory", "inhaler", 160, 540, 1.5, "ROOM", True),
    ("Ambroxol Syrup 100ml", "Ambroxol", "Respiratory", "bottle", 90, 540, 0.8, "ROOM", False),
    ("Clotrimazole Cream 15g", "Clotrimazole", "Dermatology", "tube", 75, 730, 2, "ROOM", False),
    ("Mupirocin Ointment 5g", "Mupirocin", "Dermatology", "tube", 150, 540, 0.4, "ROOM", True),
    ("Calamine Lotion 100ml", "Calamine", "Dermatology", "bottle", 85, 1095, 0.5, "ROOM", False),
]

MANUFACTURERS = ["Sunrise Pharma", "Medilab India", "Unicure Labs", "Healwell Ltd",
                 "Zenith Generics", "Biostar Pharma"]

# Mon..Sun demand multipliers
WEEKDAY = [1.15, 1.05, 1.0, 1.0, 1.05, 1.1, 0.65]
SEASONAL_UP = {"Antihistamine", "Respiratory"}   # rising demand in Oct-Nov


class Command(BaseCommand):
    help = "Load demo data (users, medicines, batches, 120 days of sales)"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=120)
        parser.add_argument("--seed", type=int, default=7)

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(opts["seed"])
        np_rng = np.random.default_rng(opts["seed"])
        days = opts["days"]
        today = date.today()
        start = today - timedelta(days=days)

        Sale.objects.all().delete()
        Batch.objects.all().delete()
        Medicine.objects.all().delete()
        Category.objects.all().delete()
        Supplier.objects.all().delete()

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@medisense.local", "admin@123")
        if not User.objects.filter(username="pharmacist").exists():
            User.objects.create_user("pharmacist", "pharmacist@medisense.local", "pharma@123",
                                     first_name="Store", last_name="Pharmacist")
        staff = User.objects.get(username="pharmacist")

        cats = {n: Category.objects.create(name=n, description=d) for n, d in CATEGORIES.items()}
        sups = [Supplier.objects.create(
            name=n, contact_person=c, lead_time_days=lt, accepts_returns=ret,
            phone=f"9{rnd.randint(100000000, 999999999)}",
            email=n.split()[0].lower() + "@example.com", address="Patna, Bihar")
            for n, c, lt, ret in SUPPLIERS]

        batch_counter = [0]

        def new_batch(med, sup, received, qty, life_frac=1.0, expiry=None):
            batch_counter[0] += 1
            expiry = expiry or received + timedelta(days=int(med.shelf_life_days * life_frac))
            mfg = min(expiry - timedelta(days=med.shelf_life_days), received)
            return Batch.objects.create(
                medicine=med, supplier=sup,
                batch_no=f"{med.name[:3].upper()}{received:%y%m}{batch_counter[0]:04d}",
                mfg_date=mfg, expiry_date=expiry, received_date=received,
                quantity_received=qty, quantity=qty,
                purchase_price=round(float(med.mrp) * rnd.uniform(0.62, 0.78), 2))

        # ----- deliberate demo scenarios, fed through the same FEFO simulation -----
        # (receive_date, quantity, expiry_date)
        special = {}
        for name in ["Aceclofenac 100mg", "Ciprofloxacin 500mg", "Doxycycline 100mg",
                     "Mupirocin Ointment 5g", "Multivitamin Syrup 200ml", "Iron Folic Acid",
                     "Calamine Lotion 100ml", "Ambroxol Syrup 100ml"]:
            # bulk purchase of a slow mover -> high expiry risk
            special[name] = [(today - timedelta(days=rnd.randint(40, 90)), rnd.randint(150, 320),
                              today + timedelta(days=rnd.randint(45, 240)))]
        rates = {m[0]: m[6] for m in MEDICINES}
        for name in ["Loperamide 2mg", "Clopidogrel 75mg", "Insulin Glargine 100IU"]:
            # old batch that expired a few days ago with a few units left
            k = rnd.randint(2, 20)
            special[name] = [(start - timedelta(days=180),
                              round(rates[name] * (days - k) * 1.1) + rnd.randint(8, 14),
                              today - timedelta(days=k))]
        for name in ["Paracetamol 500mg", "Cetirizine 10mg"]:
            # short-dated delivery of a fast mover -> near expiry but LOW risk
            special[name] = [(today - timedelta(days=2), 160, today + timedelta(days=25))]

        sales = []
        for (name, generic, cat, unit, mrp, life, rate, storage, rx) in MEDICINES:
            sup = rnd.choice(sups)
            med = Medicine.objects.create(
                name=name, generic_name=generic, category=cats[cat], unit=unit, mrp=mrp,
                manufacturer=rnd.choice(MANUFACTURERS), default_supplier=sup,
                shelf_life_days=life, min_stock=max(5, int(rate * 5)), storage=storage,
                prescription_required=rx)

            # opening stock: one older batch (partly used shelf life) + one fresher
            batches = [
                new_batch(med, sup, start - timedelta(days=rnd.randint(60, 200)),
                          max(5, int(rate * rnd.uniform(15, 40))), rnd.uniform(0.45, 0.9)),
                new_batch(med, sup, start - timedelta(days=rnd.randint(5, 30)),
                          max(5, int(rate * rnd.uniform(20, 50))), rnd.uniform(0.7, 1.0)),
            ]
            scheduled = sorted(special.get(name, []))
            for rec in [r for r in scheduled if r[0] <= start]:
                batches.append(new_batch(med, sup, rec[0], rec[1], expiry=rec[2]))
            scheduled = [r for r in scheduled if r[0] > start]

            pending_order = None
            for i in range(days):
                day = start + timedelta(days=i + 1)
                if pending_order and day >= pending_order[0]:
                    batches.append(new_batch(med, sup, day, pending_order[1],
                                             rnd.uniform(0.6, 1.0)))
                    pending_order = None
                while scheduled and scheduled[0][0] <= day:
                    rec = scheduled.pop(0)
                    batches.append(new_batch(med, sup, rec[0], rec[1], expiry=rec[2]))
                factor = WEEKDAY[day.weekday()]
                if cat in SEASONAL_UP:
                    factor *= 0.8 + 0.6 * (i / days)
                demand = int(np_rng.poisson(rate * factor))
                for b in sorted(batches, key=lambda x: (x.expiry_date, x.received_date, x.id)):
                    if demand == 0:
                        break
                    if b.quantity == 0 or b.expiry_date <= day:
                        continue
                    take = min(b.quantity, demand)
                    b.quantity -= take
                    demand -= take
                    sales.append(Sale(medicine=med, batch=b, quantity=take, unit_price=med.mrp,
                                      sale_date=day, sold_by=staff,
                                      invoice_no=f"INV{day:%y%m%d}{len(sales):05d}"))
                usable = sum(b.quantity for b in batches if b.expiry_date > day)
                if usable < rate * (sup.lead_time_days + 5) and pending_order is None:
                    pending_order = (day + timedelta(days=sup.lead_time_days),
                                     max(5, int(rate * rnd.uniform(30, 70))))
            for b in batches:
                b.save(update_fields=["quantity"])

        Sale.objects.bulk_create(sales, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Medicine.objects.count()} medicines, {Batch.objects.count()} batches, "
            f"{Sale.objects.count()} sale rows. Logins: admin/admin@123, pharmacist/pharma@123"))
