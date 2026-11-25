from decimal import Decimal
from django.db import models
from django.utils import timezone
from accounts.models import Business
from transactions.models import Transaction


class LedgerEntry(models.Model):
    ENTRY_DEBIT = "DEBIT"
    ENTRY_CREDIT = "CREDIT"
    ENTRY_TYPE_CHOICES = [
        (ENTRY_DEBIT, "Debit"),
        (ENTRY_CREDIT, "Credit"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
        null=True,
        blank=True,
    )
    account_code = models.CharField(max_length=30)
    account_name = models.CharField(max_length=120)
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    entry_date = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["entry_date", "id"]

    def __str__(self):
        return f"{self.entry_date} | {self.account_name} | {self.entry_type} {self.amount}"