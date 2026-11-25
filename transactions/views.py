from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from inventory.models import Counterparty, StockMovement
from .forms import DebtRepaymentForm, ReturnForm, SaleCreateForm
from .models import BusinessDay, Transaction, TransactionItem
import csv
from django.http import HttpResponse
from django.utils.dateparse import parse_date

def get_or_create_open_business_day(business):
    today = timezone.localdate()
    day = (
        BusinessDay.objects.filter(
            business=business,
            day_date=today,
            status=BusinessDay.STATUS_OPEN,
        )
        .order_by("-opened_at")
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
def sale_create(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    business_day = get_or_create_open_business_day(business)

    if request.method == "POST":
        form = SaleCreateForm(request.POST, business=business)
        if form.is_valid():
            payment_type = form.cleaned_data["payment_type"]
            customer_name = form.cleaned_data["customer_name"]
            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity"]
            notes = (form.cleaned_data["notes"] or "").strip()

            qty_dec = Decimal(quantity)
            total_amount = (qty_dec * product.selling_price).quantize(Decimal("0.01"))
            unit_profit = product.selling_price - product.cost_price
            profit_impact = (qty_dec * unit_profit).quantize(Decimal("0.01"))

            counterparty = None
            if payment_type == Transaction.PAY_CREDIT:
                counterparty = Counterparty.objects.filter(
                    business=business,
                    party_type=Counterparty.TYPE_CUSTOMER,
                    name__iexact=customer_name,
                ).first()
                if not counterparty:
                    counterparty = Counterparty.objects.create(
                        business=business,
                        name=customer_name,
                        party_type=Counterparty.TYPE_CUSTOMER,
                        outstanding_balance=Decimal("0.00"),
                    )
                counterparty.outstanding_balance = (
                    counterparty.outstanding_balance + total_amount
                ).quantize(Decimal("0.01"))
                counterparty.save(update_fields=["outstanding_balance"])

            new_stock = product.current_stock - quantity
            product.current_stock = new_stock
            product.save(update_fields=["current_stock"])

            StockMovement.objects.create(
                business=business,
                product=product,
                direction="OUT",
                quantity=qty_dec,
                balance_after=new_stock,
            )

            tx = Transaction.objects.create(
                business=business,
                business_day=business_day,
                counterparty=counterparty,
                created_by=request.user,
                txn_type=Transaction.TYPE_SALE,
                payment_type=payment_type,
                total_amount=total_amount,
                profit_impact=profit_impact,
                txn_date=timezone.now(),
                notes=notes,
            )

            TransactionItem.objects.create(
                transaction=tx,
                product=product,
                quantity=qty_dec,
                unit_price=product.selling_price,
                line_total=total_amount,
            )

            day_tx_profit = (
                Transaction.objects.filter(business=business, business_day=business_day)
                .aggregate(total=Sum("profit_impact"))["total"]
                or Decimal("0.00")
            ).quantize(Decimal("0.01"))
            BusinessDay.objects.filter(pk=business_day.pk).update(
                daily_profit=day_tx_profit
            )

            if payment_type == Transaction.PAY_CREDIT:
                messages.success(
                    request,
                    f"Mauzo ya Mkopo yamerekodiwa kwa {counterparty.name}: TZS {total_amount}. Deni lake sasa ni TZS {counterparty.outstanding_balance}.",
                )
            else:
                messages.success(
                    request,
                    f"Mauzo ya Cash yamerekodiwa: TZS {total_amount}.",
                )
            return redirect("transactions:sale_create")
    else:
        form = SaleCreateForm(business=business)

    recent_sales = Transaction.objects.filter(
        business=business,
        txn_type=Transaction.TYPE_SALE,
    ).exclude(notes__icontains="Return").select_related("counterparty")[:15]

    return render(
        request,
        "transactions/sale_form.html",
        {
            "business": business,
            "business_day": business_day,
            "form": form,
            "recent_sales": recent_sales,
        },
    )
@login_required
@transaction.atomic
def return_create(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    # Tarehe na siku ya biashara hujazwa otomatiki na mfumo
    business_day = get_or_create_open_business_day(business)

    if request.method == "POST":
        form = ReturnForm(request.POST, business=business)
        if form.is_valid():
            return_type = form.cleaned_data["return_type"]
            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity"]
            payment_type = form.cleaned_data["payment_type"]
            counterparty = form.cleaned_data["counterparty"]
            user_notes = (form.cleaned_data["notes"] or "").strip()

            qty_dec = Decimal(quantity)
            return_amount = (qty_dec * product.selling_price).quantize(Decimal("0.01"))
            unit_profit = product.selling_price - product.cost_price
            return_profit_impact = (qty_dec * unit_profit).quantize(Decimal("0.01"))

            if return_type == ReturnForm.RETURN_INWARDS:
                # Mteja amerudisha bidhaa: stock inaongezeka, faida inapungua kwa kiasi cha bidhaa iliyorudi
                new_stock = product.current_stock + int(qty_dec)
                product.current_stock = new_stock
                product.save(update_fields=["current_stock"])

                StockMovement.objects.create(
                    business=business,
                    product=product,
                    direction="IN",
                    quantity=qty_dec,
                    balance_after=new_stock,
                )

                profit_delta = -return_profit_impact
                label_text = "Return Inwards"

                if payment_type == Transaction.PAY_CREDIT and counterparty:
                    new_bal = counterparty.outstanding_balance - return_amount
                    if new_bal < Decimal("0.00"):
                        new_bal = Decimal("0.00")
                    counterparty.outstanding_balance = new_bal.quantize(Decimal("0.01"))
                    counterparty.save(update_fields=["outstanding_balance"])

            else:
                # Return Outwards: tunamrudishia msambazaji bidhaa, stock inapungua
                new_stock = product.current_stock - int(qty_dec)
                product.current_stock = new_stock
                product.save(update_fields=["current_stock"])

                StockMovement.objects.create(
                    business=business,
                    product=product,
                    direction="OUT",
                    quantity=qty_dec,
                    balance_after=new_stock,
                )

                profit_delta = Decimal("0.00")
                label_text = "Return Outwards"

                if payment_type == Transaction.PAY_CREDIT and counterparty:
                    new_bal = counterparty.outstanding_balance - return_amount
                    if new_bal < Decimal("0.00"):
                        new_bal = Decimal("0.00")
                    counterparty.outstanding_balance = new_bal.quantize(Decimal("0.01"))
                    counterparty.save(update_fields=["outstanding_balance"])

            full_notes = f"[{label_text} | Tarehe: {business_day.day_date}] {user_notes}".strip()

            tx = Transaction.objects.create(
                business=business,
                business_day=business_day,
                counterparty=counterparty,
                created_by=request.user,
                txn_type=Transaction.TYPE_SALE,
                payment_type=payment_type,
                total_amount=return_amount,
                profit_impact=profit_delta,
                txn_date=timezone.now(),
                notes=full_notes,
            )

            TransactionItem.objects.create(
                transaction=tx,
                product=product,
                quantity=qty_dec,
                unit_price=product.selling_price,
                line_total=return_amount,
            )

            # Sasisha Daily Profit kutokana na transactions za siku hii tu
            day_transactions_profit = (
                Transaction.objects.filter(business=business, business_day=business_day)
                .aggregate(total=Sum("profit_impact"))["total"]
                or Decimal("0.00")
            ).quantize(Decimal("0.01"))
            BusinessDay.objects.filter(pk=business_day.pk).update(
                daily_profit=day_transactions_profit
            )

            messages.success(
                request,
                f"{label_text} imehifadhiwa otomatiki tarehe {business_day.day_date}! Kiasi: TZS {return_amount} | Stock mpya: {new_stock}.",
            )
            return redirect("transactions:return_create")
    else:
        form = ReturnForm(business=business)

    recent_returns = Transaction.objects.filter(
        business=business,
        notes__icontains="Return",
    ).select_related("counterparty", "business_day")[:20]

    return render(
        request,
        "transactions/return_form.html",
        {
            "business": business,
            "business_day": business_day,
            "form": form,
            "recent_returns": recent_returns,
        },
    )

@login_required
@transaction.atomic
def close_business_day(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    current_day = get_or_create_open_business_day(business)

    if request.method == "POST":
        day_tx_profit = (
            Transaction.objects.filter(business=business, business_day=current_day)
            .aggregate(total=Sum("profit_impact"))["total"]
            or Decimal("0.00")
        ).quantize(Decimal("0.01"))

        current_day.daily_profit = day_tx_profit
        current_day.status = BusinessDay.STATUS_CLOSED
        current_day.closed_at = timezone.now()
        current_day.save(update_fields=["daily_profit", "status", "closed_at"])

        # Fungua siku mpya inayohakikisha Daily Profit inaanza 0.00
        BusinessDay.objects.create(
            business=business,
            day_date=timezone.localdate(),
            status=BusinessDay.STATUS_OPEN,
            daily_profit=Decimal("0.00"),
        )

        messages.success(
            request,
            f"Siku ya biashara imefungwa! Faida ya mzunguko uliofungwa: TZS {day_tx_profit}. Siku mpya imefunguliwa na Daily Profit imeanza 0.00.",
        )
        return redirect("transactions:close_day")

    day_transactions = Transaction.objects.filter(
        business=business, business_day=current_day
    ).select_related("counterparty")

    live_day_profit = (
        day_transactions.aggregate(total=Sum("profit_impact"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    closed_days = BusinessDay.objects.filter(
        business=business, status=BusinessDay.STATUS_CLOSED
    )[:15]

    return render(
        request,
        "transactions/close_day.html",
        {
            "business": business,
            "current_day": current_day,
            "live_day_profit": live_day_profit,
            "day_tx_count": day_transactions.count(),
            "closed_days": closed_days,
        },
    )


@login_required
def daybook_view(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    open_day = get_or_create_open_business_day(business)
    has_selection = bool(request.GET.get("report_type"))
    report_type = request.GET.get("report_type", "")
    date_str = (request.GET.get("date") or "").strip()
    download_flag = request.GET.get("download")

    base_qs = Transaction.objects.filter(business=business).select_related(
        "counterparty", "business_day"
    )
    qs = base_qs

    selected_date = parse_date(date_str) if date_str else None
    if selected_date:
        qs = qs.filter(txn_date__date=selected_date)

    if report_type == "CASH":
        qs = qs.filter(payment_type=Transaction.PAY_CASH, txn_type=Transaction.TYPE_SALE).exclude(
            notes__icontains="Return"
        )
    elif report_type == "CREDIT":
        qs = qs.filter(payment_type=Transaction.PAY_CREDIT, txn_type=Transaction.TYPE_SALE).exclude(
            notes__icontains="Return"
        )
    elif report_type == "RETURNS":
        qs = qs.filter(notes__icontains="Return")
    elif report_type == "DEBT_PAYMENTS":
        qs = qs.filter(txn_type=Transaction.TYPE_DEBT_PAYMENT)

    total_amount_sum = (
        qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    filtered_profit_sum = (
        qs.aggregate(total=Sum("profit_impact"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    open_day_profit = (
        base_qs.filter(business_day=open_day).aggregate(total=Sum("profit_impact"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    overall_tx_profit = (
        base_qs.aggregate(total=Sum("profit_impact"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    return_inwards_qs = base_qs.filter(notes__icontains="Return Inwards")
    return_outwards_qs = base_qs.filter(notes__icontains="Return Outwards")
    sales_qs = base_qs.filter(txn_type=Transaction.TYPE_SALE).exclude(notes__icontains="Return")
    debt_payments_qs = base_qs.filter(txn_type=Transaction.TYPE_DEBT_PAYMENT)

    gross_sales = (
        sales_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    return_inwards_total = (
        return_inwards_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    return_outwards_total = (
        return_outwards_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    net_sales = (gross_sales - return_inwards_total).quantize(Decimal("0.01"))
    net_tx_profit = overall_tx_profit

    total_debtors_balance = (
        Counterparty.objects.filter(
            business=business, party_type=Counterparty.TYPE_CUSTOMER
        ).aggregate(total=Sum("outstanding_balance"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    cash_sales_total = (
        sales_qs.filter(payment_type=Transaction.PAY_CASH).aggregate(total=Sum("total_amount"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    credit_sales_total = (
        sales_qs.filter(payment_type=Transaction.PAY_CREDIT).aggregate(total=Sum("total_amount"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    debt_payments_total = (
        debt_payments_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
    ).quantize(Decimal("0.01"))

    trial_balance_rows = [
        {
            "account": "Cash & Bank Receipts (Mauzo Cash + Malipo ya Madeni)",
            "debit": (cash_sales_total + debt_payments_total).quantize(Decimal("0.01")),
            "credit": Decimal("0.00"),
        },
        {
            "account": "Accounts Receivable / Madeni ya Wateja",
            "debit": total_debtors_balance,
            "credit": Decimal("0.00"),
        },
        {
            "account": "Return Inwards (Bidhaa Zilizorudishwa na Wateja)",
            "debit": return_inwards_total,
            "credit": Decimal("0.00"),
        },
        {
            "account": "Sales & Credit Turnover (Mapato ya Mauzo)",
            "debit": Decimal("0.00"),
            "credit": (gross_sales + return_outwards_total).quantize(Decimal("0.01")),
        },
        {
            "account": "Net Transaction Profit / Surplus",
            "debit": Decimal("0.00") if net_tx_profit >= Decimal("0.00") else abs(net_tx_profit).quantize(Decimal("0.01")),
            "credit": net_tx_profit.quantize(Decimal("0.01")) if net_tx_profit >= Decimal("0.00") else Decimal("0.00"),
        },
    ]

    tb_total_debit = sum(r["debit"] for r in trial_balance_rows).quantize(Decimal("0.01"))
    tb_total_credit = sum(r["credit"] for r in trial_balance_rows).quantize(Decimal("0.01"))

    if download_flag == "csv" and has_selection:
        safe_type = (report_type or "statement").lower()
        filename = f"mauzo_kiganjani_{safe_type}_{selected_date or timezone.localdate()}.csv"
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow([
            "Business",
            "Statement / Daybook",
            "Generated Date (System)",
            "Txn Date",
            "Txn Type",
            "Payment Type",
            "Counterparty",
            "Amount (TZS)",
            "Transaction Profit Impact (TZS)",
            "Notes",
        ])
        for tx in qs:
            writer.writerow([
                business.name,
                report_type,
                timezone.localdate().isoformat(),
                timezone.localtime(tx.txn_date).strftime("%Y-%m-%d %H:%M"),
                tx.get_txn_type_display(),
                tx.get_payment_type_display(),
                tx.counterparty.name if tx.counterparty else "Cash / Walk-in",
                tx.total_amount,
                tx.profit_impact,
                tx.notes,
            ])
        return response

    return render(
        request,
        "transactions/daybook.html",
        {
            "business": business,
            "open_day": open_day,
            "generated_date": timezone.localdate(),
            "has_selection": has_selection,
            "report_type": report_type,
            "date_str": date_str,
            "transactions": qs[:150] if has_selection else [],
            "total_amount_sum": total_amount_sum,
            "filtered_profit_sum": filtered_profit_sum,
            "open_day_profit": open_day_profit,
            "overall_tx_profit": overall_tx_profit,
            "gross_sales": gross_sales,
            "return_inwards_total": return_inwards_total,
            "return_outwards_total": return_outwards_total,
            "net_sales": net_sales,
            "net_tx_profit": net_tx_profit,
            "total_debtors_balance": total_debtors_balance,
            "cash_sales_total": cash_sales_total,
            "credit_sales_total": credit_sales_total,
            "debt_payments_total": debt_payments_total,
            "trial_balance_rows": trial_balance_rows,
            "tb_total_debit": tb_total_debit,
            "tb_total_credit": tb_total_credit,
        },
    )

@login_required
@transaction.atomic
def debt_list_and_repay(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    business_day = get_or_create_open_business_day(business)

    if request.method == "POST":
        form = DebtRepaymentForm(request.POST, business=business)
        if form.is_valid():
            counterparty = form.cleaned_data["counterparty"]
            paid_amount = Decimal(form.cleaned_data["amount"]).quantize(Decimal("0.01"))
            user_notes = (form.cleaned_data["notes"] or "").strip()

            new_balance = (counterparty.outstanding_balance - paid_amount).quantize(
                Decimal("0.01")
            )
            if new_balance < Decimal("0.00"):
                new_balance = Decimal("0.00")

            counterparty.outstanding_balance = new_balance
            counterparty.save(update_fields=["outstanding_balance"])

            now_ts = timezone.now()
            local_date_str = timezone.localtime(now_ts).strftime("%Y-%m-%d %H:%M")
            party_role = (
                "Mteja amelipa deni"
                if counterparty.party_type == Counterparty.TYPE_CUSTOMER
                else "Biashara imemlipa msambazaji"
            )
            summary_note = (
                f"[{party_role}] Imepunguzwa TZS {paid_amount} tarehe {local_date_str} | "
                f"Salio lililobaki: TZS {new_balance}"
            )
            full_notes = f"{summary_note} — {user_notes}" if user_notes else summary_note

            Transaction.objects.create(
                business=business,
                business_day=business_day,
                counterparty=counterparty,
                created_by=request.user,
                txn_type=Transaction.TYPE_DEBT_PAYMENT,
                payment_type=Transaction.PAY_CASH,
                total_amount=paid_amount,
                profit_impact=Decimal("0.00"),
                txn_date=now_ts,
                notes=full_notes,
            )

            messages.success(
                request,
                f"{party_role} ({counterparty.name}): TZS {paid_amount} tarehe {local_date_str}. Salio lililobaki: TZS {new_balance}.",
            )
            return redirect("transactions:debt_list")
    else:
        form = DebtRepaymentForm(business=business)

    debtors = Counterparty.objects.filter(
        business=business,
        party_type=Counterparty.TYPE_CUSTOMER,
        outstanding_balance__gt=Decimal("0.00"),
    ).order_by("name")

    suppliers_owed = Counterparty.objects.filter(
        business=business,
        party_type=Counterparty.TYPE_SUPPLIER,
        outstanding_balance__gt=Decimal("0.00"),
    ).order_by("name")

    repayment_logs = []
    repayments_qs = Transaction.objects.filter(
        business=business,
        txn_type=Transaction.TYPE_DEBT_PAYMENT,
    ).select_related("counterparty")[:30]

    for tx in repayments_qs:
        role_label = (
            "Mteja"
            if (tx.counterparty and tx.counterparty.party_type == Counterparty.TYPE_CUSTOMER)
            else "Msambazaji"
        )
        running_bal = (
            tx.counterparty.outstanding_balance if tx.counterparty else Decimal("0.00")
        )
        repayment_logs.append(
            {
                "date_reduced": tx.txn_date,
                "role_label": role_label,
                "party_name": tx.counterparty.name if tx.counterparty else "-",
                "amount_reduced": tx.total_amount,
                "remaining_balance": running_bal,
                "notes": tx.notes or "-",
            }
        )

    return render(
        request,
        "transactions/debt_list.html",
        {
            "business": business,
            "business_day": business_day,
            "form": form,
            "debtors": debtors,
            "suppliers_owed": suppliers_owed,
            "repayment_logs": repayment_logs,
        },
    )