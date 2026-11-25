from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from accounts.models import Business
from inventory.models import Counterparty, Product


class BusinessDay(models.Model):
    STATUS_OPEN = "OPEN"
    STATUS_CLOSED = "CLOSED"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Wazi"),
        (STATUS_CLOSED, "Imefungwa"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="business_days",
    )
    day_date = models.DateField(default=timezone.localdate)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    daily_profit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    class Meta:
        ordering = ["-day_date", "-opened_at"]

    def __str__(self):
        return f"{self.business.name} - {self.day_date} [{self.get_status_display()}]"


class Transaction(models.Model):
    TYPE_SALE = "SALE"
    TYPE_PURCHASE = "PURCHASE"
    TYPE_DEBT_PAYMENT = "DEBT_PAYMENT"
    TYPE_EXPENSE = "EXPENSE"
    TXN_TYPE_CHOICES = [
        (TYPE_SALE, "Mauzo"),
        (TYPE_PURCHASE, "Manunuzi / Kuingiza Stock"),
        (TYPE_DEBT_PAYMENT, "Malipo ya Deni"),
        (TYPE_EXPENSE, "Matumizi"),
    ]

    PAY_CASH = "CASH"
    PAY_CREDIT = "CREDIT"
    PAYMENT_TYPE_CHOICES = [
        (PAY_CASH, "Cash"),
        (PAY_CREDIT, "Credit"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    business_day = models.ForeignKey(
        BusinessDay,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.SET_NULL,
        related_name="transactions",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="transactions",
    )
    txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES)
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_TYPE_CHOICES,
        default=PAY_CASH,
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    profit_impact = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    txn_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-txn_date"]

    def __str__(self):
        return f"{self.get_txn_type_display()} - {self.total_amount} ({self.get_payment_type_display()})"


class TransactionItem(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="transaction_items",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=2)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"