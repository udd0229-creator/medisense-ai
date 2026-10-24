import csv
import json
from collections import Counter
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import generic

from ai_engine.forecast import forecast_medicine
from ai_engine.reorder import compute_reorder, reorder_table
from ai_engine.risk_model import predict_batches

from .forms import BatchForm, CategoryForm, MedicineForm, SaleForm, SupplierForm
from .models import Batch, Category, Medicine, Sale, Supplier
from .services import InsufficientStock, sell_fefo


# ------------------------------------------------------------------ dashboard
@login_required
def dashboard(request):
    today = date.today()
    risks = predict_batches()
    levels = Counter(r["level"] for r in risks)
    reorders = reorder_table(Medicine.objects.select_related("default_supplier"))

    sales_30 = (Sale.objects.filter(sale_date__gt=today - timedelta(days=30))
                .values("sale_date").annotate(q=Sum("quantity"),
                                              amt=Sum(F("quantity") * F("unit_price")))
                .order_by("sale_date"))
    sales_map = {r["sale_date"]: r for r in sales_30}
    days = [today - timedelta(days=i) for i in range(29, -1, -1)]

    # stock value expiring in each of the next 6 months
    months, month_values = [], []
    for m in range(6):
        start = (today.replace(day=1) + timedelta(days=32 * m)).replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        val = sum(float(b.purchase_price) * b.quantity for b in Batch.objects.in_stock()
                  .filter(expiry_date__gte=max(start, today), expiry_date__lt=end))
        months.append(start.strftime("%b %Y"))
        month_values.append(round(val, 2))

    context = {
        "kpi": {
            "medicines": Medicine.objects.count(),
            "batches": Batch.objects.in_stock().count(),
            "stock_value": sum(b.stock_value for b in Batch.objects.usable()),
            "high_risk": levels.get("High", 0),
            "expired": levels.get("Expired", 0),
            "potential_loss": sum(r["expected_loss"] for r in risks
                                  if r["level"] in ("High", "Expired")),
            "order_now": sum(1 for r in reorders if r["status"] == "Order now"),
            "sales_30": sum(float(r["amt"] or 0) for r in sales_30),
        },
        "top_risks": [r for r in risks if r["level"] in ("Expired", "High")][:8],
        "order_now": [r for r in reorders if r["status"] == "Order now"][:8],
        "chart": json.dumps({
            "risk_labels": ["Expired", "High", "Medium", "Low"],
            "risk_values": [levels.get(k, 0) for k in ["Expired", "High", "Medium", "Low"]],
            "sales_labels": [d.strftime("%d %b") for d in days],
            "sales_values": [float(sales_map[d]["amt"]) if d in sales_map else 0 for d in days],
            "expiry_labels": months, "expiry_values": month_values,
        }),
    }
    return render(request, "inventory/dashboard.html", context)


# ------------------------------------------------------------------ generic CRUD helpers
class SearchListView(LoginRequiredMixin, generic.ListView):
    paginate_by = 20
    search_fields = []

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f + "__icontains": q})
            qs = qs.filter(cond)
        return qs


class FormMixin(LoginRequiredMixin):
    template_name = "inventory/form.html"
    title = ""

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["title"] = self.title or (
            f"Edit {self.object}" if getattr(self, "object", None) else "Add")
        ctx["cancel_url"] = self.success_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Saved successfully.")
        return super().form_valid(form)


class SafeDeleteView(LoginRequiredMixin, generic.DeleteView):
    template_name = "inventory/confirm_delete.html"

    def form_valid(self, form):
        try:
            resp = super().form_valid(form)
            messages.success(self.request, "Deleted.")
            return resp
        except ProtectedError:
            messages.error(self.request, "Cannot delete: it is used by other records.")
            return redirect(self.success_url)


# ------------------------------------------------------------------ medicines
class MedicineList(SearchListView):
    model = Medicine
    template_name = "inventory/medicine_list.html"
    search_fields = ["name", "generic_name", "manufacturer", "category__name"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("category")
        cat = self.request.GET.get("category")
        if cat:
            qs = qs.filter(category_id=cat)
        return qs.order_by("name").annotate(stock=Sum("batches__quantity",
                                     filter=Q(batches__expiry_date__gt=date.today())))

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["categories"] = Category.objects.all()
        return ctx


class MedicineCreate(FormMixin, generic.CreateView):
    model = Medicine
    form_class = MedicineForm
    title = "Add Medicine"
    success_url = reverse_lazy("medicine_list")


class MedicineUpdate(FormMixin, generic.UpdateView):
    model = Medicine
    form_class = MedicineForm
    success_url = reverse_lazy("medicine_list")


class MedicineDelete(SafeDeleteView):
    model = Medicine
    success_url = reverse_lazy("medicine_list")


@login_required
def medicine_detail(request, pk):
    med = get_object_or_404(Medicine.objects.select_related("category", "default_supplier"), pk=pk)
    batches = med.batches.in_stock().select_related("supplier").fefo()
    risks = predict_batches(batches)
    fc = forecast_medicine(med)
    reorder = compute_reorder(med, fc)
    hist = fc["history"].tail(60)
    chart = {
        "labels": [d.strftime("%d %b") for d in hist.index] +
                  [d.strftime("%d %b") for d in fc["forecast"].index],
        "history": [float(v) for v in hist.values] + [None] * len(fc["forecast"]),
        "forecast": [None] * (len(hist) - 1) + [float(hist.values[-1])] +
                    [round(float(v), 2) for v in fc["forecast"].values],
    }
    return render(request, "inventory/medicine_detail.html", {
        "medicine": med, "risks": risks, "fc": fc, "reorder": reorder,
        "chart": json.dumps(chart),
        "recent_sales": med.sales.select_related("batch")[:10],
    })


# ------------------------------------------------------------------ batches
class BatchList(SearchListView):
    model = Batch
    template_name = "inventory/batch_list.html"
    search_fields = ["batch_no", "medicine__name", "supplier__name"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("medicine", "supplier")
        show = self.request.GET.get("show", "stock")
        if show == "stock":
            qs = qs.filter(quantity__gt=0)
        elif show == "expired":
            qs = qs.filter(quantity__gt=0, expiry_date__lte=date.today())
        elif show == "soon":
            qs = qs.filter(quantity__gt=0, expiry_date__gt=date.today(),
                           expiry_date__lte=date.today() + timedelta(days=90))
        return qs.order_by("expiry_date")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["show"] = self.request.GET.get("show", "stock")
        ctx["today"] = date.today()
        return ctx


class BatchCreate(FormMixin, generic.CreateView):
    model = Batch
    form_class = BatchForm
    title = "Receive New Batch"
    success_url = reverse_lazy("batch_list")

    def get_initial(self):
        init = super().get_initial()
        if self.request.GET.get("medicine"):
            init["medicine"] = self.request.GET["medicine"]
            med = Medicine.objects.filter(pk=init["medicine"]).first()
            if med and med.default_supplier_id:
                init["supplier"] = med.default_supplier_id
        if self.request.GET.get("qty"):
            init["quantity_received"] = self.request.GET["qty"]
        return init


class BatchUpdate(FormMixin, generic.UpdateView):
    model = Batch
    form_class = BatchForm
    success_url = reverse_lazy("batch_list")


class BatchDelete(SafeDeleteView):
    model = Batch
    success_url = reverse_lazy("batch_list")


# ------------------------------------------------------------------ suppliers & categories
class SupplierList(SearchListView):
    model = Supplier
    template_name = "inventory/supplier_list.html"
    search_fields = ["name", "contact_person", "phone"]


class SupplierCreate(FormMixin, generic.CreateView):
    model = Supplier
    form_class = SupplierForm
    title = "Add Supplier"
    success_url = reverse_lazy("supplier_list")


class SupplierUpdate(FormMixin, generic.UpdateView):
    model = Supplier
    form_class = SupplierForm
    success_url = reverse_lazy("supplier_list")


class SupplierDelete(SafeDeleteView):
    model = Supplier
    success_url = reverse_lazy("supplier_list")


class CategoryList(SearchListView):
    model = Category
    template_name = "inventory/category_list.html"
    search_fields = ["name"]


class CategoryCreate(FormMixin, generic.CreateView):
    model = Category
    form_class = CategoryForm
    title = "Add Category"
    success_url = reverse_lazy("category_list")


class CategoryUpdate(FormMixin, generic.UpdateView):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy("category_list")


class CategoryDelete(SafeDeleteView):
    model = Category
    success_url = reverse_lazy("category_list")


# ------------------------------------------------------------------ sales
class SaleList(SearchListView):
    model = Sale
    template_name = "inventory/sale_list.html"
    search_fields = ["medicine__name", "batch__batch_no", "invoice_no"]

    def get_queryset(self):
        return super().get_queryset().select_related("medicine", "batch", "sold_by")


@login_required
def sale_create(request):
    form = SaleForm(request.POST or None, initial={"medicine": request.GET.get("medicine")})
    if request.method == "POST" and form.is_valid():
        med = form.cleaned_data["medicine"]
        try:
            rows = sell_fefo(med, form.cleaned_data["quantity"],
                             discount_percent=form.cleaned_data["discount_percent"] or 0,
                             user=request.user)
            used = ", ".join(f"{r.batch.batch_no} × {r.quantity}" for r in rows)
            messages.success(request, f"Sold {form.cleaned_data['quantity']} {med.unit}(s) of "
                                      f"{med.name} (FEFO batches: {used}). Invoice {rows[0].invoice_no}")
            return redirect("sale_create")
        except InsufficientStock as e:
            form.add_error("quantity", str(e))
    stock = {m.id: m.usable_stock for m in Medicine.objects.all()}
    return render(request, "inventory/sale_form.html", {
        "form": form, "stock_json": json.dumps(stock),
        "recent": Sale.objects.select_related("medicine", "batch")[:10]})


# ------------------------------------------------------------------ reports
@login_required
def export_stock_csv(request):
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="stock_report_{date.today()}.csv"'
    w = csv.writer(resp)
    w.writerow(["Medicine", "Category", "Batch", "Supplier", "Mfg date", "Expiry date",
                "Days to expiry", "Quantity", "Purchase price", "Stock value"])
    for b in Batch.objects.in_stock().select_related("medicine__category", "supplier").fefo():
        w.writerow([b.medicine.name, b.medicine.category.name, b.batch_no,
                    b.supplier.name if b.supplier else "", b.mfg_date, b.expiry_date,
                    b.days_to_expiry, b.quantity, b.purchase_price, round(b.stock_value, 2)])
    return resp


@login_required
def reports(request):
    return render(request, "inventory/reports.html")
