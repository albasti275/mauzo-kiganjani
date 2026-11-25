from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from transactions.models import BusinessDay, Transaction


@login_required
def home(request):
    business = request.user.business
    if not business:
        return redirect("accounts:login")

    today = timezone.localdate()
    business_day = (
        BusinessDay.objects.filter(
            business=business,
            day_date=today,
            status=BusinessDay.STATUS_OPEN,
        )
        .order_by("-opened_at")
        .first()
    )
    if not business_day:
        business_day = BusinessDay.objects.create(
            business=business,
            day_date=today,
            status=BusinessDay.STATUS_OPEN,
            daily_profit=Decimal("0.00"),
        )

    day_profit = (
        Transaction.objects.filter(business=business, business_day=business_day)
        .aggregate(total=Sum("profit_impact"))["total"]
        or Decimal("0.00")
    ).quantize(Decimal("0.01"))
    if business_day.daily_profit != day_profit:
        business_day.daily_profit = day_profit
        business_day.save(update_fields=["daily_profit"])

    recent_activities = (
        Transaction.objects.filter(business=business)
        .select_related("counterparty", "business_day")
        .order_by("-txn_date", "-id")[:20]
    )

    context = {
        "business": business,
        "business_day": business_day,
        "today": today,
        "recent_activities": recent_activities,
    }
    return render(request, "dashboard/home.html", context)