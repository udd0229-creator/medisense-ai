import csv
import json
from collections import Counter
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from inventory.models import Category, Medicine

from .forecast import forecast_medicine
from .reorder import reorder_table
from .risk_model import load_metrics, predict_batches, train_model


@login_required
def expiry_risk(request):
    level = request.GET.get("level", "")
    category = request.GET.get("category", "")
    risks = predict_batches()
    counts = Counter(r["level"] for r in risks)
    if level:
        risks = [r for r in risks if r["level"] == level]
    if category:
        risks = [r for r in risks if str(r["batch"].medicine.category_id) == category]
    return render(request, "ai_engine/expiry_risk.html", {
        "risks": risks, "counts": counts, "level": level, "category": category,
        "categories": Category.objects.all(),
        "total_loss": sum(r["expected_loss"] for r in risks if r["level"] in ("High", "Expired")),
    })


@login_required
def expiry_risk_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="expiry_risk_{date.today()}.csv"'
    w = csv.writer(resp)
    w.writerow(["Medicine", "Batch", "Expiry date", "Days to expiry", "Quantity",
                "Avg daily sales", "Days of stock", "Risk %", "Risk level",
                "Expected unsold", "Expected loss (Rs)", "Recommended action"])
    for r in predict_batches():
        b, f = r["batch"], r["features"] or {}
        w.writerow([b.medicine.name, b.batch_no, b.expiry_date, b.days_to_expiry, b.quantity,
                    f.get("avg_daily_sales", ""), f.get("days_of_stock", ""), r["probability"],
                    r["level"], r["expected_unsold"], r["expected_loss"], r["action"]])
    return resp


@login_required
def forecast(request):
    meds = Medicine.objects.all()
    selected = meds.filter(pk=request.GET.get("medicine")).first() or \
        meds.filter(name="Cetirizine 10mg").first() or meds.first()
    ctx = {"medicines": meds, "selected": selected}
    if selected:
        fc = forecast_medicine(selected)
        hist = fc["history"]
        ctx["fc"] = fc
        ctx["chart"] = json.dumps({
            "labels": [d.strftime("%d %b") for d in hist.index] +
                      [d.strftime("%d %b") for d in fc["forecast"].index],
            "history": [float(v) for v in hist.values] + [None] * len(fc["forecast"]),
            "trend": [None if v != v else round(float(v), 2) for v in hist.rolling(7).mean().values] +
                     [None] * len(fc["forecast"]),
            "forecast": [None] * (len(hist) - 1) + [float(hist.values[-1])] +
                        [round(float(v), 2) for v in fc["forecast"].values],
        })
    return render(request, "ai_engine/forecast.html", ctx)


@login_required
def reorder(request):
    rows = reorder_table(Medicine.objects.select_related("default_supplier", "category"))
    status = request.GET.get("status", "")
    counts = Counter(r["status"] for r in rows)
    if status:
        rows = [r for r in rows if r["status"] == status]
    return render(request, "ai_engine/reorder.html", {
        "rows": rows, "status": status,
        "cards": [(k, counts.get(k, 0), c) for k, c in [
            ("Order now", "danger"), ("Overstocked", "warning"),
            ("Sufficient", "success"), ("No demand", "secondary")]],
        "total_cost": sum(r["order_cost"] for r in rows if r["status"] == "Order now"),
    })


@login_required
def reorder_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="purchase_order_{date.today()}.csv"'
    w = csv.writer(resp)
    w.writerow(["Medicine", "Supplier", "Usable stock", "Daily demand", "Lead time",
                "Safety stock", "Reorder point", "EOQ", "Shelf-life cap", "Order qty",
                "Estimated cost (Rs)", "Status"])
    for r in reorder_table(Medicine.objects.select_related("default_supplier")):
        m = r["medicine"]
        w.writerow([m.name, m.default_supplier.name if m.default_supplier else "", r["stock"],
                    r["daily_demand"], r["lead_time"], r["safety_stock"], r["reorder_point"],
                    r["eoq"], r["shelf_cap"], r["order_qty"], r["order_cost"], r["status"]])
    return resp


@login_required
def model_info(request):
    return render(request, "ai_engine/model_info.html", {"m": load_metrics()})


@require_POST
@user_passes_test(lambda u: u.is_staff)
def retrain(request):
    m = train_model()
    messages.success(request, f"Model retrained. Test accuracy {m['accuracy'] * 100:.1f}%, "
                              f"recall {m['recall'] * 100:.1f}%.")
    return redirect("model_info")
