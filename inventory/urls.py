from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.dashboard, name="dashboard"),

    path("medicines/", v.MedicineList.as_view(), name="medicine_list"),
    path("medicines/add/", v.MedicineCreate.as_view(), name="medicine_add"),
    path("medicines/<int:pk>/", v.medicine_detail, name="medicine_detail"),
    path("medicines/<int:pk>/edit/", v.MedicineUpdate.as_view(), name="medicine_edit"),
    path("medicines/<int:pk>/delete/", v.MedicineDelete.as_view(), name="medicine_delete"),

    path("batches/", v.BatchList.as_view(), name="batch_list"),
    path("batches/add/", v.BatchCreate.as_view(), name="batch_add"),
    path("batches/<int:pk>/edit/", v.BatchUpdate.as_view(), name="batch_edit"),
    path("batches/<int:pk>/delete/", v.BatchDelete.as_view(), name="batch_delete"),

    path("suppliers/", v.SupplierList.as_view(), name="supplier_list"),
    path("suppliers/add/", v.SupplierCreate.as_view(), name="supplier_add"),
    path("suppliers/<int:pk>/edit/", v.SupplierUpdate.as_view(), name="supplier_edit"),
    path("suppliers/<int:pk>/delete/", v.SupplierDelete.as_view(), name="supplier_delete"),

    path("categories/", v.CategoryList.as_view(), name="category_list"),
    path("categories/add/", v.CategoryCreate.as_view(), name="category_add"),
    path("categories/<int:pk>/edit/", v.CategoryUpdate.as_view(), name="category_edit"),
    path("categories/<int:pk>/delete/", v.CategoryDelete.as_view(), name="category_delete"),

    path("sales/", v.SaleList.as_view(), name="sale_list"),
    path("sales/new/", v.sale_create, name="sale_create"),

    path("reports/", v.reports, name="reports"),
    path("reports/stock.csv", v.export_stock_csv, name="export_stock"),
]
