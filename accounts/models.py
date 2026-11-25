from django.contrib.auth.models import AbstractUser
from django.db import models

class Business(models.Model):
    MODE_WHOLESALE = "WHOLESALE"
    MODE_RETAIL = "RETAIL"
    BUSINESS_MODE_CHOICES = [
        (MODE_WHOLESALE, "Jumla (Wholesale)"),
        (MODE_RETAIL, "Rejareja (Retail)"),
    ]

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=25)
    email = models.EmailField(blank=True, null=True)
    mode = models.CharField(max_length=20, choices=BUSINESS_MODE_CHOICES)
    is_mode_locked = models.BooleanField(default=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            orig = Business.objects.filter(pk=self.pk).values_list("mode", flat=True).first()
            if orig and orig != self.mode:
                raise ValueError("Mode ya biashara (Jumla/Rejareja) imefungwa na haiwezi kubadilishwa.")
        self.is_mode_locked = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} [{self.get_mode_display()}]"


class User(AbstractUser):
    ROLE_OWNER = "OWNER"
    ROLE_MANAGER = "MANAGER"
    ROLE_CASHIER = "CASHIER"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Mmiliki"),
        (ROLE_MANAGER, "Meneja / Mhasibu"),
        (ROLE_CASHIER, "Muuzaji"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=25, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OWNER)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.get_party_type_display()})"