from decimal import Decimal
from django.db import models
from accounts.models import Business


class Counterparty(models.Model):
    TYPE_CUSTOMER = "CUSTOMER"
    TYPE_SUPPLIER = "SUPPLIER"
    PARTY_TYPE_CHOICES = [
        (TYPE_CUSTOMER, "Mteja"),
        (TYPE_SUPPLIER, "Msambazaji"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="counterparties",
    )
    party_type = models.CharField(max_length=20, choices=PARTY_TYPE_CHOICES)
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=25, blank=True)
    outstanding_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_party_type_display()})"


class Product(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="products",
    )
    sku_code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=150)
    unit_label = models.CharField(max_length=40, default="Pcs")
    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    selling_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    current_stock = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    reorder_level = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit_label})"


class StockMovement(models.Model):
    DIR_IN = "IN"
    DIR_OUT = "OUT"
    DIRECTION_CHOICES = [
        (DIR_IN, "Ingezeko (IN)"),
        (DIR_OUT, "Punguzo (OUT)"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="stock_movements",
    )
    transaction = models.ForeignKey(
        "transactions.Transaction",
        on_delete=models.SET_NULL,
        related_name="stock_movements",
        null=True,
        blank=True,
    )
    # Tutaiunganisha na Transaction mara tutakapoweka models za transactions
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} {self.direction} {self.quantity} -> {self.balance_after}"