from decimal import Decimal
from django import forms
from inventory.models import Counterparty, Product
from .models import Transaction


class SaleCreateForm(forms.Form):
    PAYMENT_CHOICES = [
        ("", "-- Chagua Cash au Mkopo --"),
        (Transaction.PAY_CASH, "Cash"),
        (Transaction.PAY_CREDIT, "Mkopo (Credit)"),
    ]

    payment_type = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        required=True,
        label="Aina ya Mauzo (Lazima Uchague)",
    )
    customer_name = forms.CharField(
        max_length=150,
        required=False,
        label="Jina la Mteja (Lazima kwa Mkopo)",
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        required=True,
        label="Bidhaa",
    )
    quantity = forms.IntegerField(
        min_value=1,
        required=True,
        label="Idadi",
    )
    notes = forms.CharField(
        max_length=255,
        required=False,
        label="Maelezo (Hiari)",
    )

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business:
            self.fields["product"].queryset = Product.objects.filter(
                business=business
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        payment_type = cleaned_data.get("payment_type")
        customer_name = (cleaned_data.get("customer_name") or "").strip()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")

        if not payment_type:
            self.add_error("payment_type", "Lazima uchague kama mauzo ni Cash au Mkopo.")

        if payment_type == Transaction.PAY_CREDIT and not customer_name:
            self.add_error(
                "customer_name",
                "Kwa mauzo ya Mkopo, lazima uandike jina la mteja ili aonekane kwenye Mikopo.",
            )

        if product and quantity:
            if quantity > product.current_stock:
                self.add_error(
                    "quantity",
                    f"Stock haitoshi. Iliyopo kwa '{product.name}' ni {product.current_stock} {product.unit_label}.",
                )

        cleaned_data["customer_name"] = customer_name
        return cleaned_data


class DebtRepaymentForm(forms.Form):
    counterparty = forms.ModelChoiceField(
        queryset=Counterparty.objects.none(),
        required=True,
        empty_label="-- Chagua Mteja au Msambazaji --",
        label="Chagua Mteja (Anayelipa) au Msambazaji (Tunayemlipa)",
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=True,
        label="Kiasi Kinacholipwa / Kupunguzwa (TZS)",
    )
    notes = forms.CharField(
        max_length=255,
        required=False,
        label="Maelezo ya Malipo (Hiari)",
    )

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business:
            parties_with_balance = Counterparty.objects.filter(
                business=business,
                outstanding_balance__gt=Decimal("0.00"),
            ).order_by("party_type", "name")
            self.fields["counterparty"].queryset = parties_with_balance
            self.fields["counterparty"].label_from_instance = (
                lambda obj: f"[{'Mteja' if obj.party_type == Counterparty.TYPE_CUSTOMER else 'Msambazaji'}] {obj.name} — Salio: TZS {obj.outstanding_balance}"
            )

    def clean(self):
        cleaned_data = super().clean()
        counterparty = cleaned_data.get("counterparty")
        amount = cleaned_data.get("amount")

        if counterparty and amount is not None:
            paid_dec = Decimal(amount).quantize(Decimal("0.01"))
            if paid_dec > counterparty.outstanding_balance:
                self.add_error(
                    "amount",
                    f"Kiasi (TZS {paid_dec}) kimezidi salio lililobaki la {counterparty.name} (TZS {counterparty.outstanding_balance}).",
                )
        return cleaned_data

class ReturnForm(forms.Form):
    RETURN_INWARDS = "RETURN_INWARDS"
    RETURN_OUTWARDS = "RETURN_OUTWARDS"
    RETURN_CHOICES = [
        (RETURN_INWARDS, "Return Inwards (Mteja Amerudisha Bidhaa)"),
        (RETURN_OUTWARDS, "Return Outwards (Tunamrudishia Msambazaji Bidhaa)"),
    ]

    return_type = forms.ChoiceField(
        choices=RETURN_CHOICES,
        label="Aina ya Return",
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label="Chagua Bidhaa",
    )
    quantity = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Idadi / Kiasi Kilichorudishwa",
    )
    payment_type = forms.ChoiceField(
        choices=[
            (Transaction.PAY_CASH, "Cash"),
            (Transaction.PAY_CREDIT, "Credit / Akaunti ya Deni"),
        ],
        label="Aina ya Malipo / Salio",
    )
    counterparty = forms.ModelChoiceField(
        queryset=Counterparty.objects.none(),
        required=False,
        label="Mteja / Msambazaji (Hiari au Lazima kwa Credit)",
    )
    notes = forms.CharField(
        max_length=255,
        required=False,
        label="Sababu / Maelezo ya Return (Hiari)",
    )

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        if business:
            self.fields["product"].queryset = Product.objects.filter(
                business=business
            ).order_by("name")
            self.fields["counterparty"].queryset = Counterparty.objects.filter(
                business=business
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        return_type = cleaned_data.get("return_type")
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")
        counterparty = cleaned_data.get("counterparty")

        if return_type == self.RETURN_OUTWARDS and not counterparty:
            self.add_error(
                "counterparty",
                "Kwa Return Outwards, lazima uchague msambazaji unayemrudishia bidhaa.",
            )

        if product and quantity and return_type == self.RETURN_OUTWARDS:
            if Decimal(quantity) > Decimal(product.current_stock):
                self.add_error(
                    "quantity",
                    f"Stock haitoshi kurudisha kwa msambazaji. Iliyopo kwa '{product.name}' ni {product.current_stock}.",
                )
        return cleaned_data