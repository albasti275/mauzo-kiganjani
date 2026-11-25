from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from .models import Business, User


class BusinessRegistrationForm(UserCreationForm):
    business_name = forms.CharField(
        max_length=150,
        label="Jina la Biashara / Duka",
        widget=forms.TextInput(attrs={"placeholder": "Mfano: Kiganjani Traders"}),
    )
    business_phone = forms.CharField(
        max_length=25,
        label="Namba ya Simu ya Biashara",
        widget=forms.TextInput(attrs={"placeholder": "Mfano: 0712000000"}),
    )
    business_email = forms.EmailField(
        required=False,
        label="Barua Pepe ya Biashara (Hiari)",
        widget=forms.EmailInput(attrs={"placeholder": "mfano@biashara.co.tz"}),
    )
    business_mode = forms.ChoiceField(
        choices=Business.BUSINESS_MODE_CHOICES,
        label="Chagua Aina ya Biashara (Haitabadilishwa baadaye)",
        widget=forms.Select(),
    )
    full_name = forms.CharField(
        max_length=150,
        label="Jina Lako Kamili",
        widget=forms.TextInput(attrs={"placeholder": "Jina lako kamili"}),
    )
    email = forms.EmailField(
        required=True,
        label="Barua Pepe Yako (Kwa Login & Reset Password)",
        widget=forms.EmailInput(attrs={"placeholder": "wewe@mfano.com"}),
    )
    phone = forms.CharField(
        max_length=25,
        required=False,
        label="Namba Yako ya Simu",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "full_name", "email", "phone", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        business = Business.objects.create(
            name=self.cleaned_data["business_name"],
            phone=self.cleaned_data["business_phone"],
            email=self.cleaned_data.get("business_email") or None,
            mode=self.cleaned_data["business_mode"],
            is_mode_locked=True,
        )
        user = super().save(commit=False)
        user.business = business
        user.role = User.ROLE_OWNER
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        full_name = self.cleaned_data["full_name"].strip()
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ""
        if commit:
            user.save()
        return user