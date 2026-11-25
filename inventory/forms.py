from django import forms
from accounts.models import Business
from transactions.models import Transaction
from .models import Product


class ProductForm(forms.ModelForm):
    PURCHASE_PAYMENT_CHOICES = [
        ("", "-- Chagua Cash au Mkopo --"),
        (Transaction.PAY_CASH, "Cash"),
        (Transaction.PAY_CREDIT, "Mkopo (Credit)"),
    ]

    supplier_name = forms.CharField(
        max_length=150,
        required=True,
        label="Jina la Msambazaji",
    )
    purchase_payment_type = forms.ChoiceField(
        choices=PURCHASE_PAYMENT_CHOICES,
        required=True,
        label="Aina ya Manunuzi (Cash au Mkopo)",
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "unit_label",
            "cost_price",
            "selling_price",
            "current_stock",
            "reorder_level",
        ]
        labels = {
            "name": "Jina la Bidhaa",
            "unit_label": "Kipimo",
            "cost_price": "Bei ya Kununulia (Cost Price)",
            "selling_price": "Bei ya Kuuzia",
            "current_stock": "Stock ya Kuanzia (Opening Stock)",
            "reorder_level": "Kiwango cha Tahadhari (Reorder Level)",
        }

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business and not self.instance.pk:
            if business.mode == Business.MODE_WHOLESALE:
                self.fields["selling_price"].label = "Bei ya Kuuzia ya Jumla"
            else:
                self.fields["selling_price"].label = "Bei ya Kuuzia ya Rejareja"

    def clean_supplier_name(self):
        return (self.cleaned_data.get("supplier_name") or "").strip()