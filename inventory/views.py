from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from transactions.models import BusinessDay, Counterparty, Transaction
from .forms import ProductForm
from .models import Product, StockMovement


def _get_or_create_open_day(business):
    today = timezone.localdate()
    day = (
        BusinessDay.objects.filter(
            business=business,
            status=BusinessDay.STATUS_OPEN,
        )
        .order_by("-id")
        .first()
    )
    if not day:
        day = BusinessDay.objects.create(
            business=business,
            day_date=today,
            status=BusinessDay.STATUS_OPEN,
            daily_profit=Decimal("0.00"),
        )
    return day


@login_required
@transaction.atomic
def product_list(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    business_day = _get_or_create_open_day(business)

    if request.method == "POST":
        form = ProductForm(request.POST, business=business)
        if form.is_valid():
            supplier_name = form.cleaned_data["supplier_name"]
            payment_type = form.cleaned_data["purchase_payment_type"]

            product = form.save(commit=False)
            product.business = business
            product.save()

            supplier = Counterparty.objects.filter(
                business=business,
                party_type=Counterparty.TYPE_SUPPLIER,
                name__iexact=supplier_name,
            ).first()
            if not supplier:
                supplier = Counterparty.objects.create(
                    business=business,
                    name=supplier_name,
                    party_type=Counterparty.TYPE_SUPPLIER,
                    outstanding_balance=Decimal("0.00"),
                )

            if product.current_stock > 0:
                qty_dec = Decimal(product.current_stock)
                purchase_amount = (qty_dec * product.cost_price).quantize(Decimal("0.01"))

                StockMovement.objects.create(
                    business=business,
                    product=product,
                    direction=StockMovement.DIR_IN,
                    quantity=qty_dec,
                    balance_after=product.current_stock,
                )

                if payment_type == Transaction.PAY_CREDIT:
                    supplier.outstanding_balance = (
                        supplier.outstanding_balance + purchase_amount
                    ).quantize(Decimal("0.01"))
                    supplier.save(update_fields=["outstanding_balance"])

                now_ts = timezone.now()
                local_date_str = timezone.localtime(now_ts).strftime("%Y-%m-%d %H:%M")
                Transaction.objects.create(
                    business=business,
                    business_day=business_day,
                    counterparty=supplier,
                    created_by=request.user,
                    txn_type=Transaction.TYPE_PURCHASE,
                    payment_type=payment_type,
                    total_amount=purchase_amount,
                    profit_impact=Decimal("0.00"),
                    txn_date=now_ts,
                    notes=f"Manunuzi ya {product.current_stock} '{product.name}' kutoka kwa {supplier.name} ({payment_type}) tarehe {local_date_str}",
                )

            messages.success(
                request,
                f"Bidhaa '{product.name}' imehifadhiwa kwenye stock (Msambazaji: {supplier.name}).",
            )
            return redirect("inventory:product_list")
    else:
        form = ProductForm(business=business)

    products = Product.objects.filter(business=business).order_by("name")
    movements = StockMovement.objects.filter(business=business)[:15]

    return render(
        request,
        "inventory/product_list.html",
        {
            "business": business,
            "form": form,
            "products": products,
            "movements": movements,
        },
    )


@login_required
@transaction.atomic
def product_create(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    business_day = _get_or_create_open_day(business)

    if request.method == "POST":
        form = ProductForm(request.POST, business=business)
        if form.is_valid():
            supplier_name = form.cleaned_data["supplier_name"]
            payment_type = form.cleaned_data["purchase_payment_type"]

            product = form.save(commit=False)
            product.business = business
            product.save()

            supplier = Counterparty.objects.filter(
                business=business,
                party_type=Counterparty.TYPE_SUPPLIER,
                name__iexact=supplier_name,
            ).first()
            if not supplier:
                supplier = Counterparty.objects.create(
                    business=business,
                    name=supplier_name,
                    party_type=Counterparty.TYPE_SUPPLIER,
                    outstanding_balance=Decimal("0.00"),
                )

            if product.current_stock > 0:
                qty_dec = Decimal(product.current_stock)
                purchase_amount = (qty_dec * product.cost_price).quantize(Decimal("0.01"))

                StockMovement.objects.create(
                    business=business,
                    product=product,
                    direction=StockMovement.DIR_IN,
                    quantity=qty_dec,
                    balance_after=product.current_stock,
                )

                if payment_type == Transaction.PAY_CREDIT:
                    supplier.outstanding_balance = (
                        supplier.outstanding_balance + purchase_amount
                    ).quantize(Decimal("0.01"))
                    supplier.save(update_fields=["outstanding_balance"])

                now_ts = timezone.now()
                local_date_str = timezone.localtime(now_ts).strftime("%Y-%m-%d %H:%M")
                Transaction.objects.create(
                    business=business,
                    business_day=business_day,
                    counterparty=supplier,
                    created_by=request.user,
                    txn_type=Transaction.TYPE_PURCHASE,
                    payment_type=payment_type,
                    total_amount=purchase_amount,
                    profit_impact=Decimal("0.00"),
                    txn_date=now_ts,
                    notes=f"Manunuzi ya {product.current_stock} '{product.name}' kutoka kwa {supplier.name} ({payment_type}) tarehe {local_date_str}",
                )

            messages.success(
                request,
                f"Bidhaa '{product.name}' imehifadhiwa kwenye stock (Msambazaji: {supplier.name}).",
            )
            return redirect("inventory:product_list")
    else:
        form = ProductForm(business=business)

    return render(
        request,
        "inventory/product_form.html",
        {
            "business": business,
            "form": form,
        },
    )