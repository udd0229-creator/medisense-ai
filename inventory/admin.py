from django.contrib import admin

from .models import Batch, Category, Medicine, Sale, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "phone", "lead_time_days", "accepts_returns"]
    search_fields = ["name"]


class BatchInline(admin.TabularInline):
    model = Batch
    extra = 0


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "mrp", "default_supplier", "shelf_life_days"]
    list_filter = ["category", "storage", "prescription_required"]
    search_fields = ["name", "generic_name"]
    inlines = [BatchInline]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ["medicine", "batch_no", "expiry_date", "quantity", "purchase_price", "supplier"]
    list_filter = ["supplier", "expiry_date"]
    search_fields = ["batch_no", "medicine__name"]


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["sale_date", "invoice_no", "medicine", "batch", "quantity", "unit_price"]
    list_filter = ["sale_date"]
    search_fields = ["invoice_no", "medicine__name"]
