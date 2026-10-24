from datetime import date

from django import forms

from .models import Batch, Category, Medicine, Supplier


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else (
                "form-select" if isinstance(field.widget, forms.Select) else "form-control")
            field.widget.attrs.setdefault("class", css)


class CategoryForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]


class SupplierForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address",
                  "lead_time_days", "accepts_returns"]


class MedicineForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Medicine
        fields = ["name", "generic_name", "category", "manufacturer", "unit", "mrp",
                  "default_supplier", "shelf_life_days", "min_stock", "storage",
                  "prescription_required"]


class DateInput(forms.DateInput):
    input_type = "date"


class BatchForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Batch
        fields = ["medicine", "supplier", "batch_no", "mfg_date", "expiry_date",
                  "received_date", "quantity_received", "quantity", "purchase_price"]
        widgets = {"mfg_date": DateInput(), "expiry_date": DateInput(),
                   "received_date": DateInput()}
        help_texts = {"quantity": "Leave equal to quantity received for a new batch"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].required = False

    def clean(self):
        data = super().clean()
        mfg, exp = data.get("mfg_date"), data.get("expiry_date")
        received = data.get("quantity_received")
        if mfg and exp and exp <= mfg:
            self.add_error("expiry_date", "Expiry date must be after manufacturing date.")
        if mfg and mfg > date.today():
            self.add_error("mfg_date", "Manufacturing date cannot be in the future.")
        if data.get("quantity") in (None, ""):
            data["quantity"] = received
        if received is not None and data.get("quantity") is not None \
                and data["quantity"] > received:
            self.add_error("quantity", "Current quantity cannot exceed quantity received.")
        return data


class SaleForm(BootstrapMixin, forms.Form):
    medicine = forms.ModelChoiceField(queryset=Medicine.objects.all())
    quantity = forms.IntegerField(min_value=1)
    discount_percent = forms.DecimalField(min_value=0, max_value=100, initial=0,
                                          decimal_places=2, required=False)
